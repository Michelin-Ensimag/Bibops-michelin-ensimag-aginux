"""Coverage for daemon-process racing modules (helper functions only).

Each daemon main.py has `_ARGS = _parse_args()` at module level.  We import
them with a patched sys.argv so argparse sees only the script name.  After
import we exercise the pure helper functions without starting any network
connections.
"""
from __future__ import annotations

import asyncio
import importlib
import sys
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers: import a daemon module with clean argv
# ---------------------------------------------------------------------------

def _load_module(module_path: str):
    """Import module_path with sys.argv=['main.py'] to satisfy argparse."""
    # Remove any cached version so module-level _ARGS is re-created cleanly
    for key in list(sys.modules.keys()):
        if key == module_path or key.startswith(module_path + "."):
            del sys.modules[key]
    with patch("sys.argv", ["main.py"]):
        return importlib.import_module(module_path)


# ---------------------------------------------------------------------------
# team_client/main.py
# ---------------------------------------------------------------------------

class TestTeamClientHelpers:
    @pytest.fixture(scope="class")
    def mod(self):
        return _load_module("src.racing.team_client.main")

    def test_pfx_returns_string(self, mod):
        result = mod._pfx()
        assert isinstance(result, str)

    def test_banner_runs_without_error(self, mod, capsys):
        mod._banner()
        captured = capsys.readouterr()
        assert len(captured.out) > 0

    def test_log_lap_no_safety_car(self, mod, capsys):
        mod._log_lap(5, 50, "Dry", False)
        out = capsys.readouterr().out
        assert "5" in out

    def test_log_lap_with_safety_car(self, mod, capsys):
        mod._log_lap(10, 50, "Wet", True)
        out = capsys.readouterr().out
        assert "SC" in out

    def test_log_thinking(self, mod, capsys):
        mod._log_thinking()
        assert len(capsys.readouterr().out) > 0

    def test_log_decision_box_box(self, mod, capsys):
        mod._log_decision({"action": "BOX BOX", "tires": "SOFT", "fuel_added": "full", "reasoning": "wear high"}, 2.5)
        assert "BOX" in capsys.readouterr().out

    def test_log_decision_stay_out(self, mod, capsys):
        mod._log_decision({"action": "STAY OUT", "reasoning": "ok"}, 1.0)
        assert "STAY" in capsys.readouterr().out

    def test_log_posted(self, mod, capsys):
        mod._log_posted(12)
        assert "12" in capsys.readouterr().out

    def test_log_error(self, mod, capsys):
        mod._log_error("connection failed")
        out = capsys.readouterr().out
        assert "connection failed" in out

    def test_query_payload_model(self, mod):
        payload = mod._QueryPayload(payload="test")
        assert payload.payload == "test"

    def test_module_has_compiled_graph(self, mod):
        assert hasattr(mod, "compiled_graph")


# ---------------------------------------------------------------------------
# team_zero_shot/main.py
# ---------------------------------------------------------------------------

class TestTeamZeroShotHelpers:
    @pytest.fixture(scope="class")
    def mod(self):
        return _load_module("src.racing.team_zero_shot.main")

    def test_pfx_returns_string(self, mod):
        assert isinstance(mod._pfx(), str)

    def test_query_payload_model(self, mod):
        p = mod._QueryPayload(payload="hello")
        assert p.payload == "hello"

    def test_module_level_args_have_defaults(self, mod):
        assert hasattr(mod._ARGS, "team")
        assert hasattr(mod._ARGS, "model")


# ---------------------------------------------------------------------------
# team_psi/main.py
# ---------------------------------------------------------------------------

class TestTeamPsiHelpers:
    @pytest.fixture(scope="class")
    def mod(self):
        return _load_module("src.racing.team_psi.main")

    def test_pfx_returns_string(self, mod):
        assert isinstance(mod._pfx(), str)

    def test_select_target_round_robin(self, mod):
        """First N laps rotate through targets round-robin."""
        targets = mod._TARGETS
        for lap in range(1, len(targets) + 1):
            t = mod._select_target(lap)
            assert t in targets

    def test_select_target_adaptive_after_rotation(self, mod):
        """After full rotation, picks highest-vulnerability target."""
        n = len(mod._TARGETS)
        # Reset vulnerability scores
        for t in mod._TARGETS:
            mod._target_vulnerability[t] = 0
        mod._target_vulnerability[mod._TARGETS[0]] = 5
        result = mod._select_target(n + 1)
        assert result == mod._TARGETS[0]

    def test_target_vulnerability_dict_exists(self, mod):
        assert isinstance(mod._target_vulnerability, dict)
        assert all(v >= 0 for v in mod._target_vulnerability.values())


# ---------------------------------------------------------------------------
# team_validated/main.py
# ---------------------------------------------------------------------------

class TestTeamValidatedHelpers:
    @pytest.fixture(scope="class")
    def mod(self):
        return _load_module("src.racing.team_validated.main")

    def test_pfx_returns_string(self, mod):
        assert isinstance(mod._pfx(), str)

    def test_query_payload_model(self, mod):
        p = mod._QueryPayload(payload="test_query")
        assert p.payload == "test_query"


# ---------------------------------------------------------------------------
# start_arena.py — pure helper functions
# ---------------------------------------------------------------------------

class TestStartArena:
    @pytest.fixture(scope="class")
    def mod(self):
        import src.racing.start_arena as sa
        return sa

    def test_teams_config_non_empty(self, mod):
        assert len(mod.TEAMS) > 0
        for name, module, llm, port in mod.TEAMS:
            assert isinstance(name, str)
            assert isinstance(port, int)

    def test_banner_runs(self, mod, capsys):
        mod._banner()
        assert len(capsys.readouterr().out) > 0

    def test_ensure_log_dir_creates_dir(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "LOG_DIR", str(tmp_path / "logs"))
        mod._ensure_log_dir()
        assert (tmp_path / "logs").exists()

    def test_log_path_returns_string(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "LOG_DIR", str(tmp_path / "logs"))
        mod._ensure_log_dir()
        result = mod._log_path("test_team")
        assert "test_team" in result

    def test_terminate_all_empty_list(self, mod):
        mod._terminate_all([])  # should not raise


# ---------------------------------------------------------------------------
# experts.py — mock _get_llm to test node functions
# ---------------------------------------------------------------------------

class TestExpertNodes:
    def _make_llm_response(self, content: str):
        resp = MagicMock()
        resp.content = content
        return resp

    def test_tire_engineer_node_returns_messages(self):
        from src.racing.experts import tire_engineer_node
        fake_llm = MagicMock()
        fake_llm.invoke.return_value = self._make_llm_response("RECOMMANDATION PNEUS : GARDER")
        state = {"telemetry": {
            "lap_current": 5, "lap_total": 50,
            "tire_compound": "SOFT", "tire_wear_pct": 60,
            "weather_current": "Dry", "weather_forecast": "Dry",
        }}
        with patch("src.racing.experts._get_llm", return_value=fake_llm):
            result = tire_engineer_node(state)
        assert "messages" in result
        assert result["messages"][0].name == "tire_engineer"

    def test_fuel_engineer_node_returns_messages(self):
        from src.racing.experts import fuel_engineer_node
        fake_llm = MagicMock()
        fake_llm.invoke.return_value = self._make_llm_response("RECOMMANDATION CARBURANT : SUFFISANT")
        state = {"telemetry": {
            "lap_current": 10, "lap_total": 50,
            "fuel_liters": 50.0, "fuel_consumption": 1.8,
        }}
        with patch("src.racing.experts._get_llm", return_value=fake_llm):
            result = fuel_engineer_node(state)
        assert "messages" in result
        assert result["messages"][0].name == "fuel_engineer"

    def test_race_engineer_node_returns_messages(self):
        from src.racing.experts import race_engineer_node
        fake_llm = MagicMock()
        fake_llm.invoke.return_value = self._make_llm_response("RECOMMANDATION STRATÉGIE : PIT SAFE")
        state = {"telemetry": {
            "lap_current": 20, "lap_total": 50,
            "position": 3, "gap_ahead_sec": 5.2, "gap_behind_sec": 1.8,
            "lap_time_seconds": 90.5, "tire_compound": "MEDIUM", "tire_wear_pct": 55,
        }}
        with patch("src.racing.experts._get_llm", return_value=fake_llm):
            result = race_engineer_node(state)
        assert "messages" in result
        assert result["messages"][0].name == "race_engineer"


# ---------------------------------------------------------------------------
# hub/rag_service.py — mock chromadb and OllamaEmbeddings
# ---------------------------------------------------------------------------

class TestRacingRAG:
    def test_ask_question_with_results(self):
        from src.racing.hub.rag_service import RacingRAG

        fake_collection = MagicMock()
        fake_collection.query.return_value = {
            "documents": [["Michelin SOFT tyres last 20 laps."]],
            "metadatas": [[{"source": "michelin.pdf", "page": 5}]],
            "distances": [[0.1]],
        }
        fake_client = MagicMock()
        fake_client.get_collection.return_value = fake_collection
        fake_embeddings = MagicMock()
        fake_embeddings.embed_query.return_value = [0.1] * 768

        rag = RacingRAG()
        # Reset class singletons
        RacingRAG._chroma_client = fake_client
        RacingRAG._embeddings = fake_embeddings

        result = asyncio.run(rag.ask_question("Which tire compound for wet track?"))
        assert "Michelin" in result or "Source" in result

    def test_ask_question_empty_results(self):
        from src.racing.hub.rag_service import RacingRAG

        fake_collection = MagicMock()
        fake_collection.query.return_value = {"documents": [[]], "metadatas": [[]], "distances": [[]]}
        fake_client = MagicMock()
        fake_client.get_collection.return_value = fake_collection
        fake_embeddings = MagicMock()
        fake_embeddings.embed_query.return_value = [0.0] * 768

        rag = RacingRAG()
        RacingRAG._chroma_client = fake_client
        RacingRAG._embeddings = fake_embeddings

        result = asyncio.run(rag.ask_question("anything"))
        assert "RAG vide" in result or "Aucun" in result

    def test_ask_question_chromadb_error(self):
        from src.racing.hub.rag_service import RacingRAG

        fake_client = MagicMock()
        fake_client.get_collection.side_effect = RuntimeError("collection not found")

        rag = RacingRAG()
        RacingRAG._chroma_client = fake_client
        RacingRAG._embeddings = None

        result = asyncio.run(rag.ask_question("question"))
        assert "indisponible" in result or "Cause" in result

    def test_constants_accessible(self):
        from src.racing.hub.rag_service import COLLECTION_NAME, TOP_K
        assert COLLECTION_NAME == "racing_kb"
        assert isinstance(TOP_K, int) and TOP_K > 0


# ---------------------------------------------------------------------------
# team_validated/graph.py + state_tools.py
# ---------------------------------------------------------------------------

class TestTeamValidatedGraph:
    def test_compiled_graph_exists(self):
        from src.racing.team_validated.graph import compiled_graph
        assert compiled_graph is not None

    def test_route_finish_to_end(self):
        from langgraph.graph import END

        from src.racing.team_validated.graph import _route_from_telemetry_validator
        state = {"telemetry": {}, "messages": [], "next_node": "FINISH", "final_decision": None}
        assert _route_from_telemetry_validator(state) == END

    def test_route_to_expert(self):
        from src.racing.team_validated.graph import _route_from_routing
        state = {"telemetry": {}, "messages": [], "next_node": "tire_expert", "final_decision": None}
        assert _route_from_routing(state) == "tire_expert"


class TestTeamValidatedStateTools:
    def test_constants_accessible(self):
        from src.racing.team_validated.state_tools import HUB_BASE_URL, TEAM_ID
        assert "localhost" in HUB_BASE_URL or "http" in HUB_BASE_URL
        assert isinstance(TEAM_ID, str)

    def test_team_state_typeddict_usable(self):
        from src.racing.team_validated.state_tools import TeamState
        state: TeamState = {
            "telemetry": {},
            "messages": [],
            "final_decision": None,
            "next_node": "FINISH",
        }
        assert state["next_node"] == "FINISH"
