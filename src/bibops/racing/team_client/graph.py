"""
Team Client — LangGraph Assembly
Assemble le StateGraph de l'écurie et expose `compiled_graph`.

Topologie :
                  ┌──────────────────────────────┐
                  │       TEAM PRINCIPAL          │
                  │  (entry point + supervisor)   │
                  └──┬──────────────┬────────────┘
                     │              │
               tire_expert    fuel_expert
                     │              │
                  └──┴──────────────┘
                     (retournent au Principal)
                            │
                        [FINISH] ──► END
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from src.bibops.racing.team_client.nodes import (
    fuel_expert_node,
    team_principal_node,
    tire_expert_node,
)
from src.bibops.racing.team_client.state_tools import TeamState


# ---------------------------------------------------------------------------
# Routage conditionnel
# ---------------------------------------------------------------------------

def _route_from_principal(state: TeamState) -> str:
    """
    Lit `next_node` dans le state et retourne le nom du nœud cible.
    "FINISH" est mappé vers END (constante LangGraph).
    """
    next_node = state.get("next_node", "FINISH")
    if next_node == "FINISH":
        return END
    return next_node


# ---------------------------------------------------------------------------
# Construction du graphe
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    builder = StateGraph(TeamState)

    # — Nœuds —
    builder.add_node("team_principal", team_principal_node)
    builder.add_node("tire_expert",    tire_expert_node)
    builder.add_node("fuel_expert",    fuel_expert_node)

    # — Point d'entrée —
    builder.set_entry_point("team_principal")

    # — Experts retournent toujours au Team Principal —
    builder.add_edge("tire_expert", "team_principal")
    builder.add_edge("fuel_expert", "team_principal")

    # — Team Principal route conditionnellement —
    builder.add_conditional_edges(
        "team_principal",
        _route_from_principal,
        {
            "tire_expert": "tire_expert",
            "fuel_expert": "fuel_expert",
            END:           END,
        },
    )

    return builder.compile()


# Instance compilée prête à l'import
compiled_graph = build_graph()
