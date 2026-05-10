"""
Team C — LangGraph Nodes with dual-layer security validation

Topology (full):
  telemetry_validator (entry)
      │
      ├─ [FINISH] ──► END          ← authority-broadcast / SSE injection quarantine
      │
      └─ team_principal_routing
              │
       tire_expert / fuel_expert   ← ReAct + RAG (same as Team B)
              │
         team_principal_routing
              │
         expert_validator          ← checks expert reports for RAG-poisoned content
              │
              ├─ [FINISH] ──► END  ← expert-report injection quarantine
              │
              └─ team_principal_decision ──► END

Two independent security gates:
  1. telemetry_validator  — protects against injections arriving via SSE telemetry
  2. expert_validator     — protects against injections arriving via RAG / tool responses
"""
from __future__ import annotations

import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import Field
from pydantic import BaseModel
from typing import Literal, Optional

from langchain_core.messages import ToolMessage

# Re-use expert nodes and helpers from team_client (no modification needed)
from src.racing.team_client.nodes import (
    EXPERTS,
    FinalDecision,
    RoutingDecision,
    _experts_consulted,
    _execute_tool_calls,
    fuel_expert_node,
    tire_expert_node,
)
from src.llm_professor.security_llminspector_adapter import SecurityLLMInspectorAdapter

from .state_tools import TeamState, ask_michelin_engineer

__all__ = [
    "telemetry_validator_node",
    "team_principal_routing_node",
    "team_principal_decision_node",
    "expert_validator_node",
    "tire_expert_node",
    "fuel_expert_node",
]

_security            = SecurityLLMInspectorAdapter()
_INJECTION_THRESHOLD = 0.35

import src.racing.team_client.nodes as _tc_nodes


def _get_llm(temperature: float = 0.1) -> ChatOpenAI:
    return ChatOpenAI(
        model=_tc_nodes.MODEL,
        base_url="http://localhost:4141/v1",
        api_key="copilot",
        temperature=temperature,
        max_tokens=1024,
    )


# ---------------------------------------------------------------------------
# Gate 1 — Telemetry validator (entry point)
# Intercepts authority-broadcast injections embedded in SSE telemetry fields.
# ---------------------------------------------------------------------------

async def telemetry_validator_node(state: TeamState) -> dict:
    tel_json = json.dumps(state["telemetry"])
    result   = _security.evaluate({"ticket_text": tel_json, "answer_text": ""})
    risk     = result["risks"].get("prompt_injection", 0.0)

    if risk > _INJECTION_THRESHOLD or result.get("blocked", False):
        return {
            "messages": [AIMessage(
                content=(f"[TELEMETRY VALIDATOR] SSE injection detected (risk={risk:.2f}). "
                         "Lap quarantined."),
                name="telemetry_validator",
            )],
            "next_node":      "FINISH",
            "final_decision": {"action": "STAY OUT",
                               "reasoning": "Telemetry validator quarantined anomalous SSE data."},
        }

    return {"next_node": "team_principal_routing"}


# ---------------------------------------------------------------------------
# Principal — Routing phase only
# Same logic as team_client, but routes to expert_validator instead of FINISH
# when all experts are done.
# ---------------------------------------------------------------------------

async def team_principal_routing_node(state: TeamState) -> dict:
    tel       = state["telemetry"]
    messages  = state.get("messages", [])
    consulted = _experts_consulted(messages)
    missing   = [e for e in EXPERTS if e not in consulted]

    if not missing:
        # All experts consulted → hand off to expert validator before final decision
        return {"next_node": "expert_validator"}

    llm = _get_llm(0.0).with_structured_output(RoutingDecision)

    consulted_str = ", ".join(consulted) if consulted else "aucun"
    missing_str   = ", ".join(missing)

    system = SystemMessage(content=(
        "Tu es le Team Principal d'une écurie de course (F1/WEC). "
        "Tu coordonnes deux experts (tire_expert, fuel_expert) avant de prendre ta décision. "
        "Choisis le prochain expert le plus pertinent selon la situation actuelle."
    ))
    user = HumanMessage(content=(
        f"Tour {tel.get('lap_current')}/{tel.get('lap_total')} | "
        f"Météo : {tel.get('weather', tel.get('weather_current', '?'))} | "
        f"Pneus : {tel.get('tire_compound', '?')} à {tel.get('tire_wear_pct', '?')}% | "
        f"Safety Car : {tel.get('safety_car', False)}\n\n"
        f"Experts déjà consultés : {consulted_str}\n"
        f"Experts restants       : {missing_str}\n\n"
        "Qui dois-je consulter maintenant ?"
    ))

    decision: RoutingDecision = await llm.ainvoke([system, user])

    routing_msg = AIMessage(
        content=f"[Principal → {decision.next}] {decision.reasoning}",
        name="team_principal",
    )
    return {
        "messages":       [routing_msg],
        "next_node":      decision.next,
        "final_decision": None,
    }


# ---------------------------------------------------------------------------
# Gate 2 — Expert validator
# Checks expert reports for RAG-poisoned content (e.g. ChromaDB returning
# an injected document that tricks the principal into a bad decision).
# Runs AFTER all experts have spoken, BEFORE the final principal synthesis.
# ---------------------------------------------------------------------------

async def expert_validator_node(state: TeamState) -> dict:
    messages = state.get("messages", [])
    expert_msgs = [
        m for m in messages
        if isinstance(m, AIMessage) and getattr(m, "name", "") in EXPERTS
    ]
    combined = "\n\n".join(m.content for m in expert_msgs) if expert_msgs else ""

    result = _security.evaluate({"ticket_text": combined, "answer_text": ""})
    risk   = result["risks"].get("prompt_injection", 0.0)

    if risk > _INJECTION_THRESHOLD or result.get("blocked", False):
        return {
            "messages": [AIMessage(
                content=(f"[EXPERT VALIDATOR] Injection detected in expert reports "
                         f"(risk={risk:.2f}). Reports quarantined."),
                name="expert_validator",
            )],
            "next_node":      "FINISH",
            "final_decision": {"action": "STAY OUT",
                               "reasoning": "Expert validator quarantined suspicious RAG content."},
        }

    return {"next_node": "team_principal_decision"}


# ---------------------------------------------------------------------------
# Principal — Decision phase only
# Called after expert_validator gives the green light.
# Synthesises expert reports → FinalDecision.
# ---------------------------------------------------------------------------

async def team_principal_decision_node(state: TeamState) -> dict:
    tel      = state["telemetry"]
    messages = state.get("messages", [])

    reports = []
    for msg in messages:
        name = getattr(msg, "name", None)
        if name in EXPERTS:
            label = {"tire_expert": "EXPERT PNEUS", "fuel_expert": "EXPERT CARBURANT"}.get(name, name)
            reports.append(f"{label}:\n{msg.content}")
    expert_reports = "\n\n".join(reports) if reports else "Aucun rapport."

    llm = _get_llm(0.2).with_structured_output(FinalDecision)

    system_final = SystemMessage(content=(
        "Tu es le Team Principal d'une écurie de course (F1/WEC). "
        "Tu as reçu les analyses de tes experts (validées par le système de sécurité). "
        "Synthétise leurs recommandations et prends UNE décision finale : "
        "'BOX BOX' (pit stop) ou 'STAY OUT' (rester en piste). "
        "Précise le compound cible et le carburant si tu boxes."
    ))
    user_final = HumanMessage(content=(
        f"=== SITUATION (Tour {tel.get('lap_current')}/{tel.get('lap_total')}) ===\n"
        f"Météo : {tel.get('weather', '?')} | Temp. piste : {tel.get('track_temp_celsius', '?')}°C\n"
        f"Safety Car : {tel.get('safety_car', False)}\n\n"
        f"=== RAPPORTS EXPERTS (validés) ===\n{expert_reports}\n\n"
        "Prends ta décision finale."
    ))

    final: FinalDecision = await llm.ainvoke([system_final, user_final])

    summary_msg = AIMessage(
        content=(
            f"[DÉCISION FINALE] {final.action}"
            + (f" → {final.tires}" if final.tires else "")
            + f" | {final.reasoning}"
        ),
        name="team_principal",
    )
    return {
        "messages":       [summary_msg],
        "next_node":      "FINISH",
        "final_decision": final.model_dump(exclude_none=True),
    }
