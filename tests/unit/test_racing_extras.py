"""Coverage for racing pure/mockable modules: state, attack_payloads,
security_metrics, supervisor helpers, and graph routing."""
from __future__ import annotations

from langgraph.graph import END

# ---------------------------------------------------------------------------
# state.py — TypedDict definition (import only)
# ---------------------------------------------------------------------------

class TestRacingStateImport:
    def test_module_importable(self):
        from src.racing.state import RacingState
        assert RacingState is not None

    def test_can_create_state_dict(self):
        from src.racing.state import RacingState
        state: RacingState = {
            "telemetry": {"lap_current": 1, "lap_total": 50},
            "messages": [],
            "next_node": "FINISH",
        }
        assert state["next_node"] == "FINISH"


# ---------------------------------------------------------------------------
# shared/attack_payloads.py — pure data
# ---------------------------------------------------------------------------

class TestAttackPayloads:
    def test_direct_injection_non_empty(self):
        from src.racing.shared.attack_payloads import DIRECT_INJECTION
        assert len(DIRECT_INJECTION) > 0
        assert all(isinstance(p, str) for p in DIRECT_INJECTION)

    def test_authority_spoof_non_empty(self):
        from src.racing.shared.attack_payloads import AUTHORITY_SPOOF
        assert len(AUTHORITY_SPOOF) > 0

    def test_rag_poison_non_empty(self):
        from src.racing.shared.attack_payloads import RAG_POISON
        assert len(RAG_POISON) > 0

    def test_all_payloads_are_strings(self):
        from src.racing.shared import attack_payloads as ap
        for attr in ("DIRECT_INJECTION", "AUTHORITY_SPOOF", "RAG_POISON"):
            lst = getattr(ap, attr)
            for item in lst:
                assert isinstance(item, str) and len(item) > 10

    def test_random_payload_function_exists(self):
        """Module should expose a way to get a random payload or just the lists."""
        import src.racing.shared.attack_payloads as ap
        # Verify the module loaded all lists without error
        assert hasattr(ap, "DIRECT_INJECTION")


# ---------------------------------------------------------------------------
# shared/security_metrics.py — dataclasses + detect functions
# ---------------------------------------------------------------------------

class TestAttackEventDataclass:
    def test_creation(self):
        from src.racing.shared.security_metrics import AttackEvent
        ev = AttackEvent(
            lap=5,
            attacker="team_psi",
            target="team_a",
            attack_type="direct_injection",
            payload="ignore previous",
            response="SOFT compound, pit lap 20",
            injection_executed=True,
            data_leaked=True,
            detected=False,
        )
        assert ev.lap == 5
        assert ev.injection_executed is True

    def test_false_values(self):
        from src.racing.shared.security_metrics import AttackEvent
        ev = AttackEvent(
            lap=1, attacker="psi", target="b",
            attack_type="t", payload="p", response="r",
            injection_executed=False, data_leaked=False, detected=False,
        )
        assert ev.injection_executed is False
        assert ev.data_leaked is False
        assert ev.detected is False


class TestTeamSecurityMetrics:
    def test_creation_and_to_dict(self):
        from src.racing.shared.security_metrics import TeamSecurityMetrics
        m = TeamSecurityMetrics(team_id="team_b")
        assert m.attacks_received == 0
        d = m.to_dict()
        assert d["team_id"] == "team_b"
        assert "attacks_received" in d

    def test_attack_event_list(self):
        from src.racing.shared.security_metrics import AttackEvent, TeamSecurityMetrics
        m = TeamSecurityMetrics(team_id="team_c")
        ev = AttackEvent(
            lap=3, attacker="psi", target="c", attack_type="rag",
            payload="p", response="r",
            injection_executed=False, data_leaked=False, detected=False,
        )
        m.attack_events.append(ev)
        assert len(m.attack_events) == 1


class TestDetectFunctions:
    def test_injection_executed_on_compound(self):
        from src.racing.shared.security_metrics import detect_injection_executed
        assert detect_injection_executed("My tire_compound is SOFT") is True

    def test_injection_not_executed_on_normal(self):
        from src.racing.shared.security_metrics import detect_injection_executed
        assert detect_injection_executed("Stay out, conditions are good") is False

    def test_refusal_with_strategy_words_is_not_injection(self):
        from src.racing.shared.security_metrics import detect_injection_executed
        response = "I cannot disclose sensitive strategic information about pit stop strategy."
        assert detect_injection_executed(response) is False

    def test_data_leaked_on_pit_lap(self):
        from src.racing.shared.security_metrics import detect_data_leaked
        assert detect_data_leaked("pit_lap: 25 is our plan") is True

    def test_data_not_leaked_on_normal(self):
        from src.racing.shared.security_metrics import detect_data_leaked
        assert detect_data_leaked("We recommend staying out") is False

    def test_self_detection_positive(self):
        from src.racing.shared.security_metrics import detect_self_detection
        assert detect_self_detection("Suspicious injection attempt detected, blocked.") is True

    def test_self_detection_negative(self):
        from src.racing.shared.security_metrics import detect_self_detection
        assert detect_self_detection("Recommend pit stop now") is False


# ---------------------------------------------------------------------------
# supervisor.py — pure helper functions (no LLM calls)
# ---------------------------------------------------------------------------

class TestExpertsAlreadyConsulted:
    def test_empty_messages(self):
        from src.racing.supervisor import _experts_already_consulted
        assert _experts_already_consulted([]) == []

    def test_single_expert(self):
        from langchain_core.messages import AIMessage

        from src.racing.supervisor import _experts_already_consulted
        msgs = [AIMessage(content="Tires OK", name="tire_engineer")]
        assert _experts_already_consulted(msgs) == ["tire_engineer"]

    def test_no_duplicate_experts(self):
        from langchain_core.messages import AIMessage

        from src.racing.supervisor import _experts_already_consulted
        msgs = [
            AIMessage(content="Round 1", name="tire_engineer"),
            AIMessage(content="Round 2", name="tire_engineer"),
        ]
        result = _experts_already_consulted(msgs)
        assert result.count("tire_engineer") == 1

    def test_messages_without_name_ignored(self):
        from langchain_core.messages import HumanMessage

        from src.racing.supervisor import _experts_already_consulted
        msgs = [HumanMessage(content="Human input")]
        assert _experts_already_consulted(msgs) == []

    def test_all_three_experts(self):
        from langchain_core.messages import AIMessage

        from src.racing.supervisor import EXPERTS, _experts_already_consulted
        msgs = [AIMessage(content="ok", name=e) for e in EXPERTS]
        result = _experts_already_consulted(msgs)
        assert set(result) == set(EXPERTS)


class TestFormatExpertReports:
    def test_empty_messages_returns_fallback(self):
        from src.racing.supervisor import _format_expert_reports
        result = _format_expert_reports([])
        assert "Aucun" in result

    def test_single_expert_formatted(self):
        from langchain_core.messages import AIMessage

        from src.racing.supervisor import _format_expert_reports
        msgs = [AIMessage(content="Pneus usés à 80%", name="tire_engineer")]
        result = _format_expert_reports(msgs)
        assert "Pneus usés à 80%" in result
        assert "INGÉNIEUR PNEUS" in result

    def test_non_expert_messages_excluded(self):
        from langchain_core.messages import AIMessage, HumanMessage

        from src.racing.supervisor import _format_expert_reports
        msgs = [
            HumanMessage(content="Human msg"),
            AIMessage(content="Expert fuel report", name="fuel_engineer"),
        ]
        result = _format_expert_reports(msgs)
        assert "Human msg" not in result
        assert "Expert fuel report" in result


# ---------------------------------------------------------------------------
# graph.py — route function + compiled_graph import
# ---------------------------------------------------------------------------

class TestRoutingFunction:
    def test_finish_routes_to_end(self):
        from src.racing.graph import _route_from_supervisor
        state = {"telemetry": {}, "messages": [], "next_node": "FINISH"}
        result = _route_from_supervisor(state)
        assert result == END

    def test_tire_engineer_routes_correctly(self):
        from src.racing.graph import _route_from_supervisor
        state = {"telemetry": {}, "messages": [], "next_node": "tire_engineer"}
        assert _route_from_supervisor(state) == "tire_engineer"

    def test_default_missing_key_is_finish(self):
        from src.racing.graph import _route_from_supervisor
        state = {"telemetry": {}, "messages": []}  # no next_node key
        result = _route_from_supervisor(state)
        assert result == END

    def test_compiled_graph_is_not_none(self):
        from src.racing.graph import compiled_graph
        assert compiled_graph is not None


# ---------------------------------------------------------------------------
# team_client/graph.py — route function + compiled_graph
# ---------------------------------------------------------------------------

class TestTeamClientGraph:
    def test_route_finish_to_end(self):
        from src.racing.team_client.graph import _route_from_principal
        state = {"telemetry": {}, "messages": [], "next_node": "FINISH", "final_decision": None}
        assert _route_from_principal(state) == END

    def test_route_to_expert(self):
        from src.racing.team_client.graph import _route_from_principal
        state = {"telemetry": {}, "messages": [], "next_node": "tire_expert", "final_decision": None}
        assert _route_from_principal(state) == "tire_expert"

    def test_compiled_graph_exists(self):
        from src.racing.team_client.graph import compiled_graph
        assert compiled_graph is not None
