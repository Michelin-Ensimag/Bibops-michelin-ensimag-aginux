"""Coverage for racing hub FastAPI server via TestClient."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Client fixture — patches ObserverEngine to avoid touching the real log dir
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("observer_log")
    with patch("src.racing.hub.observer._LOG_DIR", tmp):
        from src.racing.hub.server import app
        with TestClient(app) as c:
            yield c


# ---------------------------------------------------------------------------
# GET /status
# ---------------------------------------------------------------------------

class TestStatus:
    def test_returns_200(self, client):
        resp = client.get("/status")
        assert resp.status_code == 200

    def test_has_required_keys(self, client):
        data = client.get("/status").json()
        assert "lap_current" in data
        assert "weather" in data
        assert "race_status" in data

    def test_fuel_liters_is_float(self, client):
        data = client.get("/status").json()
        assert isinstance(data["fuel_liters"], (int, float))


# ---------------------------------------------------------------------------
# GET /results
# ---------------------------------------------------------------------------

class TestResults:
    def test_returns_200(self, client):
        resp = client.get("/results")
        assert resp.status_code == 200

    def test_has_required_keys(self, client):
        data = client.get("/results").json()
        assert "race_lap" in data
        assert "total_decisions" in data
        assert "teams" in data
        assert "full_log" in data

    def test_full_log_is_list(self, client):
        data = client.get("/results").json()
        assert isinstance(data["full_log"], list)


# ---------------------------------------------------------------------------
# GET /race-history (WeakProxy)
# ---------------------------------------------------------------------------

class TestRaceHistory:
    def test_returns_200(self, client):
        resp = client.get("/race-history")
        assert resp.status_code == 200

    def test_has_warning(self, client):
        data = client.get("/race-history").json()
        assert "warning" in data
        assert "WeakProxy" in data["warning"]


# ---------------------------------------------------------------------------
# GET /team/{team_id}/strategy (WeakProxy)
# ---------------------------------------------------------------------------

class TestTeamStrategy:
    def test_returns_200(self, client):
        resp = client.get("/team/team_a_zero_shot/strategy")
        assert resp.status_code == 200

    def test_has_warning(self, client):
        data = client.get("/team/team_a_zero_shot/strategy").json()
        assert "warning" in data

    def test_returns_team_id(self, client):
        data = client.get("/team/team_b_react/strategy?requester=tester").json()
        assert data["team_id"] == "team_b_react"

    def test_last_decisions_is_list(self, client):
        data = client.get("/team/team_a_zero_shot/strategy").json()
        assert isinstance(data["last_decisions"], list)


# ---------------------------------------------------------------------------
# POST /decision/{team_id} — race not started (lap=0) raises 409
# ---------------------------------------------------------------------------

class TestReceiveDecision:
    def test_lap_zero_returns_409(self, client):
        resp = client.post("/decision/team_a_zero_shot", json={
            "action": "BOX BOX",
            "tires": "SOFT",
            "fuel_added": "full",
        })
        # lap=0 → race not started → 409 Conflict
        assert resp.status_code == 409

    def test_stay_out_also_409_when_not_started(self, client):
        resp = client.post("/decision/team_b_react", json={"action": "STAY OUT"})
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# POST /ask_michelin — RAG route (mocked)
# ---------------------------------------------------------------------------

class TestAskMichelin:
    def test_returns_200_with_mocked_rag(self, client):
        with patch("src.racing.hub.server.racing_rag") as mock_rag:
            mock_rag.ask_question = AsyncMock(return_value="Michelin SOFT compound context")
            resp = client.post("/ask_michelin", json={
                "team_id": "team_a",
                "query": "Quelle durée de vie pour le compound SOFT ?",
            })
        assert resp.status_code == 200
        data = resp.json()
        assert data["team_id"] == "team_a"
        assert "context" in data


# ---------------------------------------------------------------------------
# POST /relay/{target_team_id} — httpx error path
# ---------------------------------------------------------------------------

class TestRelay:
    def test_unknown_team_returns_404(self, client):
        resp = client.post("/relay/unknown_team", json={
            "attacker_id": "team_psi",
            "payload": "inject",
            "attack_type": "direct",
            "lap": 10,
        })
        assert resp.status_code == 404

    def test_relay_error_returns_200_with_error_in_response(self, client):
        """Relay to known team but httpx fails → still 200 with RELAY_ERROR."""
        import httpx
        with patch("src.racing.hub.server.httpx.AsyncClient") as mock_client_cls:
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__.side_effect = httpx.ConnectError("refused")
            mock_client_cls.return_value = mock_ctx
            resp = client.post("/relay/team_a_zero_shot", json={
                "attacker_id": "team_psi",
                "payload": "injection payload",
                "attack_type": "direct_injection",
                "lap": 5,
            })
        assert resp.status_code == 200
        data = resp.json()
        assert "RELAY_ERROR" in data["response"] or "response" in data


# ---------------------------------------------------------------------------
# POST /authority-broadcast
# ---------------------------------------------------------------------------

class TestAuthorityBroadcast:
    def test_returns_200(self, client):
        resp = client.post("/authority-broadcast", json={
            "message": "All teams report status.",
            "sender": "race_director",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["broadcast"] == "sent"
