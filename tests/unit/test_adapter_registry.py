"""Unit tests for the adapter registry — selection by name + dispatch."""
from __future__ import annotations

import pytest

from src.bibops.adapters.registry import AVAILABLE_ADAPTERS, load_adapter


class TestAvailable:
    def test_known_adapter_names(self):
        assert set(AVAILABLE_ADAPTERS) == {"it_support", "openai_compat", "a2a"}


class TestLoadAdapter:
    def test_load_openai_compat(self):
        adapter = load_adapter("openai_compat", model="gpt-test", api_key="k", base_url="http://x/v1")
        assert adapter.name == "openai_compat"
        assert adapter.model == "gpt-test"

    def test_load_a2a_with_explicit_url(self):
        adapter = load_adapter("a2a", a2a_url="https://demo.test")
        assert adapter.name == "a2a"
        assert adapter.a2a_url == "https://demo.test"

    def test_load_it_support_does_not_eagerly_load_ollama(self):
        # Constructing the adapter should not import maestro/tools.
        # If imports were eager, this would fail in environments without Ollama installed.
        adapter = load_adapter("it_support", model="phi3:latest")
        assert adapter.name == "it_support"
        assert adapter._tools is None
        assert adapter._lancer is None

    def test_unknown_adapter_raises_with_helpful_message(self):
        with pytest.raises(ValueError, match="Unknown adapter"):
            load_adapter("not-a-real-adapter")
