"""Pydantic schema for probe data files."""
from __future__ import annotations

from pydantic import BaseModel, Field


class Probe(BaseModel):
    id: str
    input: str
    context: str = ""
    expected_behavior: str = ""
    tags: list[str] = Field(default_factory=list)
    severity: str = "major"
    metadata: dict = Field(default_factory=dict)


class ProbeSet(BaseModel):
    category: str
    version: int = 1
    probes: list[Probe]
