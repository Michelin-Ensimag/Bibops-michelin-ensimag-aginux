"""Tests for racing team nodes — pure helpers and mocked async node functions."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.racing.team_client.nodes import (
    EXPERTS,
    FinalDecision,
    RoutingDecision,
    _experts_consulted,
)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class TestPydanticModels:
    def test_routing_decision_valid(self):
        rd = RoutingDecision(next="tire_expert", reasoning="Need tire analysis")
        assert rd.next == "tire_expert"

    def test_routing_decision_finish(self):
        rd = RoutingDecision(next="FINISH", reasoning="All done")
        assert rd.next == "FINISH"

    def test_routing_decision_invalid_literal(self):
        with pytest.raises(Exception):
            RoutingDecision(next="invalid_expert", reasoning="bad")

    def test_final_decision_stay_out(self):
        fd = FinalDecision(action="STAY OUT", reasoning="Fuel ok, tires ok")
        assert fd.action == "STAY OUT"
        assert fd.tires is None

    def test_final_decision_box_box(self):
        fd = FinalDecision(action="BOX BOX", tires="SOFT", fuel_added="full", reasoning="Worn tires")
        assert fd.action == "BOX BOX"
        assert fd.tires == "SOFT"
        assert fd.fuel_added == "full"

    def test_final_decision_model_dump_excludes_none(self):
        fd = FinalDecision(action="STAY OUT", reasoning="all good")
        d = fd.model_dump(exclude_none=True)
        assert "tires" not in d
        assert "fuel_added" not in d


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

class TestExpertsConsulted:
    def test_empty_messages(self):
        assert _experts_consulted([]) == []

    def test_single_expert(self):
        msgs = [AIMessage(content="ok", name="tire_expert")]
        result = _experts_consulted(msgs)
        assert result == ["tire_expert"]

    def test_both_experts(self):
        msgs = [
            AIMessage(content="ok", name="tire_expert"),
            AIMessage(content="ok", name="fuel_expert"),
        ]
        result = _experts_consulted(msgs)
        assert "tire_expert" in result
        assert "fuel_expert" in result

    def test_no_duplicates(self):
        msgs = [
            AIMessage(content="first", name="tire_expert"),
            AIMessage(content="second", name="tire_expert"),
        ]
        result = _experts_consulted(msgs)
        assert result.count("tire_expert") == 1

    def test_ignores_non_expert_messages(self):
        msgs = [
            AIMessage(content="routing", name="team_principal"),
            HumanMessage(content="telemetry"),
        ]
        result = _experts_consulted(msgs)
        assert result == []

    def test_experts_constant(self):
        assert "tire_expert" in EXPERTS
        assert "fuel_expert" in EXPERTS


# ---------------------------------------------------------------------------
# Async node functions with mocked LLM
# ---------------------------------------------------------------------------

def _fake_llm_response(content: str) -> MagicMock:
    """Return a mock ChatOpenAI that always returns content."""
    msg = AIMessage(content=content)
    msg.tool_calls = []
    llm = MagicMock()
    llm.bind_tools.return_value = llm
    llm.ainvoke = AsyncMock(return_value=msg)
    return llm


def _fake_structured_llm(obj) -> MagicMock:
    llm = MagicMock()
    llm.with_structured_output.return_value = MagicMock(
        ainvoke=AsyncMock(return_value=obj)
    )
    return llm


class TestTireExpertNode:
    def test_returns_tire_expert_message(self):
        telemetry = {
            "lap_current": 5,
            "lap_total": 15,
            "tire_compound": "MEDIUM",
            "tire_wear_pct": 30.0,
            "weather": "Ensoleillé",
            "track_temp_celsius": 42.0,
            "laps_remaining": 10,
        }
        state = {"telemetry": telemetry, "messages": []}

        from src.racing.team_client.nodes import tire_expert_node
        with patch("src.racing.team_client.nodes._get_llm", return_value=_fake_llm_response("RECOMMANDATION PNEUS : GARDER")):
            result = asyncio.run(tire_expert_node(state))

        assert "messages" in result
        assert len(result["messages"]) == 1
        assert result["messages"][0].name == "tire_expert"


class TestFuelExpertNode:
    def test_returns_fuel_expert_message(self):
        telemetry = {
            "lap_current": 5,
            "lap_total": 15,
            "fuel_liters": 70.0,
            "fuel_consumption": 1.8,
            "laps_remaining": 10,
        }
        state = {"telemetry": telemetry, "messages": []}

        from src.racing.team_client.nodes import fuel_expert_node
        with patch("src.racing.team_client.nodes._get_llm", return_value=_fake_llm_response("RECOMMANDATION CARBURANT : SUFFISANT")):
            result = asyncio.run(fuel_expert_node(state))

        assert "messages" in result
        assert result["messages"][0].name == "fuel_expert"


class TestTeamPrincipalNodeRouting:
    def test_routes_to_first_expert_when_none_consulted(self):
        telemetry = {
            "lap_current": 3,
            "lap_total": 15,
            "weather": "Ensoleillé",
            "tire_compound": "MEDIUM",
            "tire_wear_pct": 20.0,
            "safety_car": False,
        }
        state = {"telemetry": telemetry, "messages": []}
        routing = RoutingDecision(next="tire_expert", reasoning="Start with tires")

        from src.racing.team_client.nodes import team_principal_node
        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = MagicMock(
            ainvoke=AsyncMock(return_value=routing)
        )
        with patch("src.racing.team_client.nodes._get_llm", return_value=mock_llm):
            result = asyncio.run(team_principal_node(state))

        assert result["next_node"] == "tire_expert"
        assert result["final_decision"] is None

    def test_produces_final_decision_when_all_experts_consulted(self):
        telemetry = {
            "lap_current": 10,
            "lap_total": 15,
            "weather": "Ensoleillé",
            "tire_compound": "MEDIUM",
            "tire_wear_pct": 70.0,
            "safety_car": False,
            "track_temp_celsius": 40.0,
        }
        messages = [
            AIMessage(content="GARDER", name="tire_expert"),
            AIMessage(content="SUFFISANT", name="fuel_expert"),
        ]
        state = {"telemetry": telemetry, "messages": messages}
        final = FinalDecision(action="STAY OUT", reasoning="All good")

        from src.racing.team_client.nodes import team_principal_node
        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = MagicMock(
            ainvoke=AsyncMock(return_value=final)
        )
        with patch("src.racing.team_client.nodes._get_llm", return_value=mock_llm):
            result = asyncio.run(team_principal_node(state))

        assert result["next_node"] == "FINISH"
        assert result["final_decision"] is not None
        assert result["final_decision"]["action"] == "STAY OUT"
