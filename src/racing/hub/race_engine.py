"""
Racing Hub — Race Engine
Moteur de course asynchrone avec broadcast SSE multi-clients.

Architecture broadcast :
  - Un seul `_race_loop()` tourne en arrière-plan (tâche asyncio).
  - Chaque client SSE obtient sa propre `asyncio.Queue` via `subscribe()`.
  - Tous les clients reçoivent la même télémétrie en même temps.
  - INITIAL_WAIT_SECONDS laisse le temps à toutes les écuries de se connecter
    avant que le premier tour soit émis.

Paramètres de simulation :
  - Course : 50 tours, 1 tour = 3 secondes
  - Météo  : Ensoleillé → Pluie légère (T15) → Pluie forte (T30) → Séchant (T42)
  - Carburant : 90 L, ~1.8 L/tour
  - Pneus : MEDIUM au départ, usure progressive
"""

import asyncio
import json
import random
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Modèle d'état de la course
# ---------------------------------------------------------------------------

@dataclass
class RaceState:
    lap_current: int = 0
    lap_total: int = 15
    weather: str = "Ensoleillé"
    track_temp_celsius: float = 42.0
    air_temp_celsius: float = 24.0
    safety_car: bool = False
    # Carburant
    fuel_liters: float = 90.0
    fuel_consumption: float = 1.8
    # Pneus
    tire_compound: str = "MEDIUM"
    tire_wear_pct: float = 0.0
    # Perf
    lap_time_seconds: float = 120.0
    # Interne
    _safety_car_laps_remaining: int = field(default=0, repr=False)

    def to_dict(self) -> dict:
        return {
            "lap_current":        self.lap_current,
            "lap_total":          self.lap_total,
            "laps_remaining":     self.lap_total - self.lap_current,
            "weather":            self.weather,
            "track_temp_celsius": round(self.track_temp_celsius, 1),
            "air_temp_celsius":   round(self.air_temp_celsius, 1),
            "safety_car":         self.safety_car,
            "fuel_liters":        round(self.fuel_liters, 2),
            "fuel_consumption":   self.fuel_consumption,
            "tire_compound":      self.tire_compound,
            "tire_wear_pct":      round(self.tire_wear_pct, 1),
            "lap_time_seconds":   self.lap_time_seconds,
            "race_status":        "FINISHED" if self.lap_current >= self.lap_total else "RUNNING",
        }


# ---------------------------------------------------------------------------
# Moteur principal
# ---------------------------------------------------------------------------

class RaceEngine:
    """
    Moteur de simulation broadcast.

    Un seul `_race_loop` s'exécute en arrière-plan et publie chaque tour
    dans toutes les queues des clients SSE connectés.
    """

    LAP_DURATION_SECONDS  = 10   # enough for multi-LLM-call teams to respond per lap
    INITIAL_WAIT_SECONDS  = 8    # attente avant le premier tour (toutes les écuries se connectent)

    WEATHER_LIGHT_RAIN_LAP = 5
    WEATHER_HEAVY_RAIN_LAP = 9
    WEATHER_DRY_AGAIN_LAP  = 12

    SC_PROBABILITY   = 0.04
    SC_DURATION_LAPS = 3

    def __init__(self) -> None:
        self._state       = RaceState()
        self._subscribers: list[asyncio.Queue] = []
        self._race_task:   asyncio.Task | None = None

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    @property
    def state(self) -> RaceState:
        return self._state

    def apply_pit_stop(self, tires: str | None, fuel_added: str | None) -> None:
        """Applique un pit stop : change les pneus et ravitaille."""
        if tires:
            self._state.tire_compound = tires.upper()
        self._state.tire_wear_pct = 0.0

        if fuel_added in (None, "full"):
            self._state.fuel_liters = 90.0
        elif fuel_added == "partial":
            self._state.fuel_liters = min(90.0, self._state.fuel_liters + 30.0)

    async def subscribe(self) -> AsyncGenerator[str, None]:
        """
        Abonne un client SSE au flux de télémétrie.
        Démarre la course automatiquement au premier abonnement.
        Le client reçoit tous les tours depuis le début grâce à INITIAL_WAIT_SECONDS.
        """
        q: asyncio.Queue = asyncio.Queue(maxsize=30)
        self._subscribers.append(q)

        # Démarre la boucle de course si elle n'est pas encore active
        if self._race_task is None or self._race_task.done():
            self._race_task = asyncio.create_task(self._race_loop())

        try:
            while True:
                event = await q.get()
                yield event
                # Terminer après race_over
                try:
                    payload = json.loads(event[len("data: "):].strip())
                    if payload.get("event") == "race_over":
                        break
                except Exception:
                    pass
        finally:
            if q in self._subscribers:
                self._subscribers.remove(q)

    # ------------------------------------------------------------------
    # Boucle de course (background task)
    # ------------------------------------------------------------------

    async def _race_loop(self) -> None:
        """Tâche asyncio : simule la course et diffuse vers tous les abonnés."""
        self._state = RaceState()

        # Attente initiale : laisse le temps à toutes les écuries de se connecter
        print(
            f"[HUB] ⏳ Course dans {self.INITIAL_WAIT_SECONDS}s "
            f"(attente des écuries)..."
        )
        await asyncio.sleep(self.INITIAL_WAIT_SECONDS)
        print(f"[HUB] 🚦 COURSE DÉMARRÉE — {len(self._subscribers)} écurie(s) connectée(s)")

        while self._state.lap_current < self._state.lap_total:
            self._state.lap_current += 1
            self._tick_weather()
            self._tick_safety_car()
            self._tick_fuel_and_tires()

            await self._broadcast(self._sse_event(self._state.to_dict()))
            await asyncio.sleep(self.LAP_DURATION_SECONDS)

        # Événement de fin de course
        final = {**self._state.to_dict(), "event": "race_over"}
        await self._broadcast(self._sse_event(final))
        print("[HUB] 🏁 Course terminée.")

    async def inject_event(self, event_data: dict) -> None:
        """Push an arbitrary event into the SSE stream (used by authority-broadcast)."""
        await self._broadcast(self._sse_event(event_data))

    async def _broadcast(self, event: str) -> None:
        """Envoie un événement SSE à tous les abonnés actifs."""
        for q in self._subscribers[:]:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # abonné trop lent — événement ignoré

    # ------------------------------------------------------------------
    # Simulation interne
    # ------------------------------------------------------------------

    def _tick_weather(self) -> None:
        lap = self._state.lap_current

        if lap < self.WEATHER_LIGHT_RAIN_LAP:
            self._state.weather = "Ensoleillé"
            self._state.track_temp_celsius = max(42.0 - lap * 0.1, 38.0)
            self._state.air_temp_celsius   = 24.0

        elif lap < self.WEATHER_HEAVY_RAIN_LAP:
            self._state.weather = "Pluie légère"
            p = (lap - self.WEATHER_LIGHT_RAIN_LAP) / (
                self.WEATHER_HEAVY_RAIN_LAP - self.WEATHER_LIGHT_RAIN_LAP
            )
            self._state.track_temp_celsius = 38.0 - p * 10.0
            self._state.air_temp_celsius   = 24.0 - p * 4.0

        elif lap < self.WEATHER_DRY_AGAIN_LAP:
            self._state.weather = "Pluie forte"
            self._state.track_temp_celsius = max(
                28.0 - (lap - self.WEATHER_HEAVY_RAIN_LAP) * 0.3, 20.0
            )
            self._state.air_temp_celsius = 18.0

        else:
            self._state.weather = "Séchant"
            p = (lap - self.WEATHER_DRY_AGAIN_LAP) / (
                self._state.lap_total - self.WEATHER_DRY_AGAIN_LAP
            )
            self._state.track_temp_celsius = 20.0 + p * 12.0
            self._state.air_temp_celsius   = 18.0 + p * 3.0

    def _tick_safety_car(self) -> None:
        if self._state._safety_car_laps_remaining > 0:
            self._state._safety_car_laps_remaining -= 1
            self._state.safety_car = True
            if self._state._safety_car_laps_remaining == 0:
                self._state.safety_car = False
            return

        if self._state.weather == "Pluie forte":
            self._state.safety_car = False
            return

        if random.random() < self.SC_PROBABILITY:
            self._state.safety_car = True
            self._state._safety_car_laps_remaining = self.SC_DURATION_LAPS

    def _tick_fuel_and_tires(self) -> None:
        # Carburant
        self._state.fuel_liters = max(
            0.0, self._state.fuel_liters - self._state.fuel_consumption
        )

        # Usure pneus
        base_wear = {
            "SOFT": 3.5, "MEDIUM": 2.2, "HARD": 1.4,
            "INTERMEDIATE": 1.1, "WET": 0.8,
        }.get(self._state.tire_compound.upper(), 2.2)

        is_rain       = "Pluie" in self._state.weather
        is_dry_cpd    = self._state.tire_compound.upper() in ("SOFT", "MEDIUM", "HARD")
        is_wet_cpd    = self._state.tire_compound.upper() in ("WET", "INTERMEDIATE")
        if is_rain and is_dry_cpd:
            base_wear += 3.0
        elif not is_rain and is_wet_cpd:
            base_wear += 5.0

        self._state.tire_wear_pct = min(100.0, self._state.tire_wear_pct + base_wear)

        # Temps au tour
        wear_penalty    = max(0.0, (self._state.tire_wear_pct - 50) * 0.08)
        weather_penalty = {"Pluie légère": 4.0, "Pluie forte": 14.0, "Séchant": 2.0}.get(
            self._state.weather, 0.0
        )
        sc_delta = 30.0 if self._state.safety_car else 0.0
        self._state.lap_time_seconds = round(
            120.0 + wear_penalty + weather_penalty + sc_delta, 3
        )

    @staticmethod
    def _sse_event(data: dict) -> str:
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
