"""Adapter registry — single entry point to instantiate any agent adapter."""
from __future__ import annotations

from src.bibops.adapters.base import AbstractAgentAdapter

AVAILABLE_ADAPTERS = ("it_support", "openai_compat", "a2a")


def load_adapter(name: str, **kwargs) -> AbstractAgentAdapter:
    """
    Instantiate an adapter by name.

    Examples:
        load_adapter("it_support")
        load_adapter("it_support", model="mistral:latest")
        load_adapter("openai_compat", model="gpt-4o-mini")
        load_adapter("a2a")                        # reads EVAL_BANK_A2A_URL from env
        load_adapter("a2a", a2a_url="https://...")
    """
    if name == "it_support":
        from src.bibops.adapters.it_support import ITSupportAdapter
        return ITSupportAdapter(**kwargs)
    if name == "openai_compat":
        from src.bibops.adapters.openai_compat import OpenAICompatAdapter
        return OpenAICompatAdapter(**kwargs)
    if name == "a2a":
        from src.bibops.adapters.a2a import A2AAdapter
        return A2AAdapter(**kwargs)
    raise ValueError(
        f"Unknown adapter: {name!r}. Available: {AVAILABLE_ADAPTERS}"
    )
