"""
Team C — LangGraph Assembly (dual-layer security validation)

Full topology:
  telemetry_validator (entry)
      │
      ├─ [FINISH] ──► END                 ← SSE injection quarantine
      │
      └─ team_principal_routing
              │
       ┌──────┴──────┐
  tire_expert    fuel_expert              ← ReAct + RAG (same as Team B)
       └──────┬──────┘
              │
         team_principal_routing
              │
         expert_validator                 ← RAG-poison / expert-report injection check
              │
              ├─ [FINISH] ──► END         ← expert-report injection quarantine
              │
              └─ team_principal_decision ──► END
"""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from .nodes import (
    expert_validator_node,
    fuel_expert_node,
    team_principal_decision_node,
    team_principal_routing_node,
    telemetry_validator_node,
    tire_expert_node,
)
from .state_tools import TeamState


# ---------------------------------------------------------------------------
# Routing helpers
# ---------------------------------------------------------------------------

def _route_from_telemetry_validator(state: TeamState) -> str:
    nxt = state.get("next_node", "team_principal_routing")
    return END if nxt == "FINISH" else "team_principal_routing"


def _route_from_routing(state: TeamState) -> str:
    nxt = state.get("next_node", "expert_validator")
    if nxt == "tire_expert":
        return "tire_expert"
    if nxt == "fuel_expert":
        return "fuel_expert"
    return "expert_validator"   # all experts done


def _route_from_expert_validator(state: TeamState) -> str:
    nxt = state.get("next_node", "team_principal_decision")
    return END if nxt == "FINISH" else "team_principal_decision"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    builder = StateGraph(TeamState)

    builder.add_node("telemetry_validator",    telemetry_validator_node)
    builder.add_node("team_principal_routing", team_principal_routing_node)
    builder.add_node("tire_expert",            tire_expert_node)
    builder.add_node("fuel_expert",            fuel_expert_node)
    builder.add_node("expert_validator",       expert_validator_node)
    builder.add_node("team_principal_decision", team_principal_decision_node)

    builder.set_entry_point("telemetry_validator")

    builder.add_conditional_edges(
        "telemetry_validator",
        _route_from_telemetry_validator,
        {"team_principal_routing": "team_principal_routing", END: END},
    )

    builder.add_edge("tire_expert", "team_principal_routing")
    builder.add_edge("fuel_expert", "team_principal_routing")

    builder.add_conditional_edges(
        "team_principal_routing",
        _route_from_routing,
        {
            "tire_expert":      "tire_expert",
            "fuel_expert":      "fuel_expert",
            "expert_validator": "expert_validator",
        },
    )

    builder.add_conditional_edges(
        "expert_validator",
        _route_from_expert_validator,
        {"team_principal_decision": "team_principal_decision", END: END},
    )

    builder.add_edge("team_principal_decision", END)

    return builder.compile()


compiled_graph = build_graph()
