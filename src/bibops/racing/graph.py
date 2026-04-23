"""
Racing MAS — LangGraph Assembly
Assemble le StateGraph et expose `compiled_graph` prêt à l'emploi.

Topologie :
                    ┌─────────────────────────────┐
                    │         SUPERVISOR           │
                    │  (entry point + router)      │
                    └──┬──────────┬───────────┬───┘
                       │          │           │
              tire_engineer  fuel_engineer  race_engineer
                       │          │           │
                    └──┴──────────┴───────────┘
                       (tous retournent au supervisor)
                               │
                           [FINISH] ──► END
"""

from langgraph.graph import END, StateGraph

from src.bibops.racing.experts import (
    fuel_engineer_node,
    race_engineer_node,
    tire_engineer_node,
)
from src.bibops.racing.state import RacingState
from src.bibops.racing.supervisor import supervisor_node


# ---------------------------------------------------------------------------
# Fonction de routage conditionnel
# ---------------------------------------------------------------------------

def _route_from_supervisor(state: RacingState) -> str:
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
    builder = StateGraph(RacingState)

    # — Nœuds —
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("tire_engineer", tire_engineer_node)
    builder.add_node("fuel_engineer", fuel_engineer_node)
    builder.add_node("race_engineer", race_engineer_node)

    # — Point d'entrée —
    builder.set_entry_point("supervisor")

    # — Experts retournent toujours au Supervisor —
    builder.add_edge("tire_engineer", "supervisor")
    builder.add_edge("fuel_engineer", "supervisor")
    builder.add_edge("race_engineer", "supervisor")

    # — Supervisor route conditionnellement —
    builder.add_conditional_edges(
        "supervisor",
        _route_from_supervisor,
        {
            "tire_engineer": "tire_engineer",
            "fuel_engineer": "fuel_engineer",
            "race_engineer": "race_engineer",
            END: END,
        },
    )

    return builder.compile()


# Instance compilée prête à l'import
compiled_graph = build_graph()
