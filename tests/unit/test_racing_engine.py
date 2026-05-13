"""Tests for RaceEngine and RaceState — sync/pure methods only."""
from __future__ import annotations

import asyncio
import json

from src.racing.hub.race_engine import RaceEngine, RaceState


class TestRaceState:
    def test_to_dict_has_required_keys(self):
        state = RaceState()
        d = state.to_dict()
        for key in ("lap_current", "lap_total", "laps_remaining", "weather",
                    "fuel_liters", "tire_compound", "tire_wear_pct", "race_status"):
            assert key in d

    def test_to_dict_initial_race_status_is_running(self):
        state = RaceState()
        assert state.to_dict()["race_status"] == "RUNNING"

    def test_to_dict_finished_when_lap_current_equals_total(self):
        state = RaceState(lap_current=15, lap_total=15)
        assert state.to_dict()["race_status"] == "FINISHED"

    def test_to_dict_laps_remaining_correct(self):
        state = RaceState(lap_current=5, lap_total=15)
        assert state.to_dict()["laps_remaining"] == 10

    def test_to_dict_rounded_values(self):
        state = RaceState(fuel_liters=87.123456, tire_wear_pct=33.99)
        d = state.to_dict()
        # Should be rounded to 2 decimal places
        assert d["fuel_liters"] == round(87.123456, 2)
        assert d["tire_wear_pct"] == round(33.99, 1)


class TestRaceEngineApplyPitStop:
    def test_apply_pit_stop_resets_tire_wear(self):
        engine = RaceEngine()
        engine._state.tire_wear_pct = 75.0
        engine.apply_pit_stop(tires="SOFT", fuel_added=None)
        assert engine._state.tire_wear_pct == 0.0

    def test_apply_pit_stop_changes_tire_compound(self):
        engine = RaceEngine()
        engine.apply_pit_stop(tires="wet", fuel_added=None)
        assert engine._state.tire_compound == "WET"

    def test_apply_pit_stop_full_fuel(self):
        engine = RaceEngine()
        engine._state.fuel_liters = 20.0
        engine.apply_pit_stop(tires=None, fuel_added="full")
        assert engine._state.fuel_liters == 90.0

    def test_apply_pit_stop_partial_fuel(self):
        engine = RaceEngine()
        engine._state.fuel_liters = 40.0
        engine.apply_pit_stop(tires=None, fuel_added="partial")
        assert engine._state.fuel_liters == 70.0  # 40 + 30

    def test_apply_pit_stop_partial_fuel_capped_at_90(self):
        engine = RaceEngine()
        engine._state.fuel_liters = 80.0
        engine.apply_pit_stop(tires=None, fuel_added="partial")
        assert engine._state.fuel_liters == 90.0  # min(90, 80+30)

    def test_apply_pit_stop_none_tires_no_compound_change(self):
        engine = RaceEngine()
        engine._state.tire_compound = "MEDIUM"
        engine.apply_pit_stop(tires=None, fuel_added=None)
        assert engine._state.tire_compound == "MEDIUM"


class TestRaceEngineWeatherTick:
    def test_tick_weather_sunny_early_laps(self):
        engine = RaceEngine()
        engine._state.lap_current = 2
        engine._tick_weather()
        assert engine._state.weather == "Ensoleillé"

    def test_tick_weather_light_rain(self):
        engine = RaceEngine()
        engine._state.lap_current = RaceEngine.WEATHER_LIGHT_RAIN_LAP
        engine._tick_weather()
        assert engine._state.weather == "Pluie légère"

    def test_tick_weather_heavy_rain(self):
        engine = RaceEngine()
        engine._state.lap_current = RaceEngine.WEATHER_HEAVY_RAIN_LAP
        engine._tick_weather()
        assert engine._state.weather == "Pluie forte"

    def test_tick_weather_dry_again(self):
        engine = RaceEngine()
        engine._state.lap_current = RaceEngine.WEATHER_DRY_AGAIN_LAP
        engine._tick_weather()
        assert engine._state.weather == "Séchant"

    def test_tick_weather_after_dry_lap(self):
        engine = RaceEngine()
        engine._state.lap_current = engine._state.lap_total  # last lap
        engine._tick_weather()
        # Should be dry or any weather — no error
        assert isinstance(engine._state.weather, str)


class TestRaceEngineTiresAndFuel:
    def test_tick_fuel_decreases_each_lap(self):
        engine = RaceEngine()
        initial_fuel = engine._state.fuel_liters
        engine._state.lap_current = 1
        engine._tick_fuel_and_tires()
        assert engine._state.fuel_liters < initial_fuel

    def test_tick_fuel_not_negative(self):
        engine = RaceEngine()
        engine._state.fuel_liters = 0.5
        engine._state.fuel_consumption = 1.8
        engine._tick_fuel_and_tires()
        assert engine._state.fuel_liters >= 0.0

    def test_tick_tire_wear_increases(self):
        engine = RaceEngine()
        initial_wear = engine._state.tire_wear_pct
        engine._state.lap_current = 5
        engine._state.weather = "Ensoleillé"
        engine._tick_fuel_and_tires()
        assert engine._state.tire_wear_pct >= initial_wear

    def test_tick_tire_wear_capped_at_100(self):
        engine = RaceEngine()
        engine._state.tire_wear_pct = 99.0
        engine._state.lap_current = 30
        engine._state.weather = "Pluie forte"
        engine._tick_fuel_and_tires()
        assert engine._state.tire_wear_pct <= 100.0


class TestRaceEngineSseEvent:
    def test_sse_event_format(self):
        engine = RaceEngine()
        state = RaceState()
        event = engine._sse_event(state.to_dict())
        assert event.startswith("data: ")
        payload = json.loads(event[len("data: "):].strip())
        assert "lap_current" in payload

    def test_sse_event_includes_arbitrary_keys(self):
        engine = RaceEngine()
        event = engine._sse_event({"event": "race_over", "lap_current": 15})
        payload = json.loads(event[len("data: "):].strip())
        assert payload["event"] == "race_over"


class TestRaceEngineBroadcast:
    def test_broadcast_to_subscriber(self):
        engine = RaceEngine()
        q = asyncio.Queue()
        engine._subscribers.append(q)

        asyncio.run(engine._broadcast("data: test\n\n"))
        assert not q.empty()
        assert q.get_nowait() == "data: test\n\n"

    def test_broadcast_skips_full_queue(self):
        engine = RaceEngine()
        q = asyncio.Queue(maxsize=1)
        q.put_nowait("already_full")
        engine._subscribers.append(q)
        # Should not raise even when queue is full
        asyncio.run(engine._broadcast("data: overflow\n\n"))
        assert q.qsize() == 1  # still 1, overflow ignored


class TestRaceEngineSafetyCarTick:
    def test_safety_car_can_be_deployed(self):
        """Run many ticks and verify safety_car is at least sometimes set (probabilistic)."""
        engine = RaceEngine()
        engine.SC_PROBABILITY = 1.0  # force deployment
        engine._state.lap_current = 1
        engine._tick_safety_car()
        assert engine._state.safety_car is True or engine._state._safety_car_laps_remaining > 0

    def test_safety_car_clears_after_duration(self):
        engine = RaceEngine()
        engine._state.safety_car = True
        engine._state._safety_car_laps_remaining = 1
        engine._tick_safety_car()
        assert engine._state._safety_car_laps_remaining == 0
        assert engine._state.safety_car is False
