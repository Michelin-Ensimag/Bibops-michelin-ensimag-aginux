"""Unit tests for the benchmark output schema (versioning + round-trip)."""
from __future__ import annotations

import json
from datetime import datetime

from src.bibops.evaluation.result_schema import SCHEMA_VERSION, build_benchmark_payload


def _payload():
    return build_benchmark_payload(
        config={"agent_model": "phi3:latest", "max_tickets": 10},
        summary={"llm_unique": {"cout_usd": 0.01}},
        quality={"llm_unique": {"score_moyen": 8.0}},
        security={"llm_unique": {"security_score_moyen": 7.5}},
        composite={"winner": "llm_unique"},
        details=[{"ticket_id": "T01", "score": 8.0}],
    )


class TestSchemaVersion:
    def test_payload_advertises_schema_version(self):
        payload = _payload()
        assert payload["schema_version"] == SCHEMA_VERSION
        assert SCHEMA_VERSION  # non-empty

    def test_schema_version_is_semver_like(self):
        parts = SCHEMA_VERSION.split(".")
        assert len(parts) == 3 and all(p.isdigit() for p in parts)


class TestPayloadShape:
    def test_top_level_keys_present(self):
        payload = _payload()
        for key in ("schema_version", "generated_at_utc", "config", "summary", "quality", "security", "composite", "details"):
            assert key in payload

    def test_generated_at_utc_is_iso8601(self):
        payload = _payload()
        # Round-trip via fromisoformat → must succeed
        dt = datetime.fromisoformat(payload["generated_at_utc"])
        assert dt.tzinfo is not None  # must be timezone-aware

    def test_payload_is_json_serializable(self):
        payload = _payload()
        # Force a round-trip to surface unserializable values
        roundtripped = json.loads(json.dumps(payload, default=str))
        assert roundtripped["schema_version"] == SCHEMA_VERSION
        assert roundtripped["details"][0]["ticket_id"] == "T01"

    def test_inputs_are_passed_through_unchanged(self):
        payload = _payload()
        assert payload["config"]["agent_model"] == "phi3:latest"
        assert payload["composite"]["winner"] == "llm_unique"
        assert payload["details"][0]["score"] == 8.0
