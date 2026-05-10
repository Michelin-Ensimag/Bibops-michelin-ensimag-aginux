"""Unit tests for the EvaluatorRegistry contract."""
from __future__ import annotations

import pytest

from src.bibops.evaluation.registry import EvaluatorRegistry


class _Stub:
    def __init__(self, name: str, score: float = 1.0, raises: Exception | None = None):
        self.name = name
        self._score = score
        self._raises = raises

    def evaluate(self, sample):
        if self._raises is not None:
            raise self._raises
        return {"status": "ok", "score": self._score, "echo": sample.get("ticket_text", "")}


class TestRegister:
    def test_register_one(self):
        reg = EvaluatorRegistry()
        reg.register(_Stub("quality"))
        assert [e.name for e in reg.evaluators] == ["quality"]

    def test_register_preserves_insertion_order(self):
        reg = EvaluatorRegistry()
        reg.register(_Stub("a"))
        reg.register(_Stub("b"))
        reg.register(_Stub("c"))
        assert [e.name for e in reg.evaluators] == ["a", "b", "c"]

    def test_register_rejects_duplicates(self):
        reg = EvaluatorRegistry()
        reg.register(_Stub("quality"))
        with pytest.raises(ValueError, match="already registered"):
            reg.register(_Stub("quality"))


class TestRunAll:
    def test_runs_each_evaluator_once(self):
        reg = EvaluatorRegistry()
        reg.register(_Stub("a", score=1.0))
        reg.register(_Stub("b", score=2.0))
        out = reg.run_all({"ticket_text": "hi"})
        assert set(out.keys()) == {"a", "b"}
        assert out["a"]["score"] == 1.0
        assert out["b"]["score"] == 2.0

    def test_isolates_failures(self):
        """A failing evaluator should not stop the others."""
        reg = EvaluatorRegistry()
        reg.register(_Stub("ok", score=5.0))
        reg.register(_Stub("crash", raises=RuntimeError("boom")))
        reg.register(_Stub("after", score=7.0))
        out = reg.run_all({"ticket_text": "x"})
        assert out["ok"]["status"] == "ok"
        assert out["crash"]["status"] == "error"
        assert "boom" in out["crash"]["error"]
        assert out["after"]["status"] == "ok"

    def test_empty_registry_returns_empty_dict(self):
        assert EvaluatorRegistry().run_all({}) == {}

    def test_sample_is_passed_through(self):
        reg = EvaluatorRegistry()
        reg.register(_Stub("echo"))
        out = reg.run_all({"ticket_text": "hello world"})
        assert out["echo"]["echo"] == "hello world"
