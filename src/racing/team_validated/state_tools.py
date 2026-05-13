"""Team C — State & Tools (identical contract to team_client, separate identity)."""
from __future__ import annotations

import operator
from typing import Annotated, TypedDict

import httpx
from langchain_core.messages import BaseMessage
from langchain_core.tools import tool

HUB_BASE_URL = "http://localhost:8000"
TEAM_ID      = "team_c_validated"


class TeamState(TypedDict):
    telemetry:      dict
    messages:       Annotated[list[BaseMessage], operator.add]
    final_decision: dict | None
    next_node:      str


@tool
async def ask_michelin_engineer(question: str) -> str:
    """
    Interroge la base documentaire officielle Michelin Motorsport hébergée
    sur le Hub pour obtenir des spécifications techniques sur les pneus,
    les composés, les conditions météo ou les procédures de pit stop.

    Args:
        question: Question technique en langage naturel (français ou anglais).

    Returns:
        Extraits bruts de la documentation Michelin les plus pertinents.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{HUB_BASE_URL}/ask_michelin",
            json={"team_id": TEAM_ID, "query": question},
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("context", "[Aucune documentation trouvée]")
