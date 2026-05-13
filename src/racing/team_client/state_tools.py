"""
Team Client — State & Tools
Définit l'état partagé du graphe LangGraph et l'outil RAG vers le Hub.
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

import httpx
from langchain_core.messages import BaseMessage
from langchain_core.tools import tool

# ---------------------------------------------------------------------------
# URL du Hub (source unique de vérité)
# ---------------------------------------------------------------------------

HUB_BASE_URL = "http://localhost:8000"
TEAM_ID      = "team_alpha"


# ---------------------------------------------------------------------------
# State partagé du graphe
# ---------------------------------------------------------------------------

class TeamState(TypedDict):
    """
    État mutable partagé par tous les nœuds de l'écurie.

    - telemetry    : snapshot du tour courant (dict du Hub SSE)
    - messages     : historique des messages LLM (accumulé par operator.add)
    - final_decision : décision stratégique finale produite par le Team Principal
    - next_node    : signal de routage interne (écrit par team_principal)
    """
    telemetry:      dict
    messages:       Annotated[list[BaseMessage], operator.add]
    final_decision: dict | None
    next_node:      str


# ---------------------------------------------------------------------------
# Outil RAG : consulte la documentation Michelin Motorsport via le Hub
# ---------------------------------------------------------------------------

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
