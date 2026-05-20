"""
Team Client — LangGraph Nodes
Trois agents : tire_expert, fuel_expert, team_principal (supervisor).

Modèle : claude-sonnet-4.6 via proxy Copilot → http://localhost:4141/v1
         Si le proxy rejette ce modèle, remplacez MODEL par "gpt-4o".
"""

from __future__ import annotations

from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from .state_tools import TeamState, ask_michelin_engineer

# ---------------------------------------------------------------------------
# Configuration LLM
# ---------------------------------------------------------------------------

MODEL = "gpt-4o"   # claude-sonnet-4.6 rejeté par le backend Copilot (model_not_supported)

EXPERTS = ["tire_expert", "fuel_expert"]


def _get_llm(temperature: float = 0.1) -> ChatOpenAI:
    return ChatOpenAI(
        model=MODEL,
        base_url="http://localhost:4141/v1",
        api_key="copilot",
        temperature=temperature,
        max_tokens=1024,
    )


# ---------------------------------------------------------------------------
# Schémas Pydantic pour les sorties structurées
# ---------------------------------------------------------------------------

class RoutingDecision(BaseModel):
    """Décision de routage du Team Principal vers le prochain expert."""
    next: Literal["tire_expert", "fuel_expert", "FINISH"] = Field(
        description=(
            "Prochain expert à consulter, ou 'FINISH' si tous les avis "
            "ont été recueillis pour prendre la décision finale."
        )
    )
    reasoning: str = Field(description="Justification courte (1-2 phrases).")


class FinalDecision(BaseModel):
    """Décision stratégique finale communiquée au Hub."""
    action: Literal["STAY OUT", "BOX BOX"] = Field(
        description="'BOX BOX' pour rentrer aux stands, 'STAY OUT' pour rester en piste."
    )
    tires: str | None = Field(
        default=None,
        description="Composé cible si BOX BOX (ex: 'WET', 'INTERMEDIATE', 'SOFT').",
    )
    fuel_added: str | None = Field(
        default=None,
        description="Carburant à ajouter si BOX BOX (ex: 'full', 'partial', 'none').",
    )
    reasoning: str = Field(description="Justification radio courte (2-3 phrases max).")


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------

def _experts_consulted(messages: list) -> list[str]:
    """Retourne les experts ayant déjà répondu dans l'historique du tour."""
    seen = []
    for msg in messages:
        name = getattr(msg, "name", None)
        if name in EXPERTS and name not in seen:
            seen.append(name)
    return seen


async def _execute_tool_calls(response: AIMessage) -> list[ToolMessage]:
    """Exécute les tool_calls d'une AIMessage et retourne les ToolMessages."""
    tool_map = {ask_michelin_engineer.name: ask_michelin_engineer}
    results = []
    for tc in response.tool_calls:
        fn = tool_map.get(tc["name"])
        if fn:
            output = await fn.ainvoke(tc["args"])
            results.append(ToolMessage(content=str(output), tool_call_id=tc["id"]))
    return results


# ---------------------------------------------------------------------------
# 1. Tire Expert
# ---------------------------------------------------------------------------

async def tire_expert_node(state: TeamState) -> dict:
    """
    Analyse les pneus et la météo.
    Peut appeler `ask_michelin_engineer` pour consulter les specs techniques.
    Termine par : RECOMMANDATION PNEUS : [GARDER / CHANGER → compound].
    """
    tel = state["telemetry"]
    llm = _get_llm(temperature=0.1).bind_tools([ask_michelin_engineer])

    system = SystemMessage(content=(
        "Tu es l'Expert Pneus d'une écurie de course (F1/WEC). "
        "Tu analyses uniquement les données pneus et météo pour formuler une recommandation chiffrée. "
        "Si tu as besoin de vérifier des spécifications techniques Michelin, utilise l'outil ask_michelin_engineer. "
        "Sois concis. Termine TOUJOURS par : "
        "RECOMMANDATION PNEUS : [GARDER / CHANGER → compound]."
    ))

    user = HumanMessage(content=(
        f"=== TÉLÉMÉTRIE PNEUS & MÉTÉO (Tour {tel.get('lap_current')}/{tel.get('lap_total')}) ===\n"
        f"Compound actuel  : {tel.get('tire_compound', 'inconnu')}\n"
        f"Usure            : {tel.get('tire_wear_pct', '?')}%\n"
        f"Météo actuelle   : {tel.get('weather', tel.get('weather_current', '?'))}\n"
        f"Temp. piste      : {tel.get('track_temp_celsius', '?')}°C\n"
        f"Tours restants   : {tel.get('laps_remaining', tel.get('lap_total', 50) - tel.get('lap_current', 0))}\n\n"
        "Analyse et donne ta recommandation. "
        "Consulte la doc Michelin si tu as besoin de specs sur les composés."
    ))

    conversation: list = [system, user]

    # Mini ReAct : max 3 itérations (LLM → tool → LLM → ...)
    for _ in range(3):
        response = await llm.ainvoke(conversation)
        conversation.append(response)

        if not response.tool_calls:
            break

        tool_msgs = await _execute_tool_calls(response)
        conversation.extend(tool_msgs)

    # Dernière réponse LLM sans tool_calls
    final_content = next(
        (m.content for m in reversed(conversation)
         if isinstance(m, AIMessage) and not getattr(m, "tool_calls", [])),
        "Analyse pneus indisponible."
    )

    return {
        "messages": [AIMessage(content=final_content, name="tire_expert")]
    }


# ---------------------------------------------------------------------------
# 2. Fuel Expert
# ---------------------------------------------------------------------------

async def fuel_expert_node(state: TeamState) -> dict:
    """
    Calcule la consommation et évalue si le carburant est suffisant.
    Termine par : RECOMMANDATION CARBURANT : [SUFFISANT / CRITIQUE / MAPPING REQUIS].
    """
    tel   = state["telemetry"]
    llm   = _get_llm(temperature=0.1)

    laps_left   = tel.get("laps_remaining", tel.get("lap_total", 50) - tel.get("lap_current", 0))
    fuel        = tel.get("fuel_liters", 0.0)
    consumption = tel.get("fuel_consumption", 1.8)
    needed      = laps_left * consumption
    margin      = fuel - needed

    system = SystemMessage(content=(
        "Tu es l'Ingénieur Carburant d'une écurie de course (F1/WEC). "
        "Tu analyses uniquement le budget carburant. Sois précis et chiffré. "
        "Termine TOUJOURS par : "
        "RECOMMANDATION CARBURANT : [SUFFISANT / CRITIQUE / MAPPING REQUIS]."
    ))

    user = HumanMessage(content=(
        f"=== TÉLÉMÉTRIE CARBURANT (Tour {tel.get('lap_current')}/{tel.get('lap_total')}) ===\n"
        f"Carburant restant    : {fuel:.1f} L\n"
        f"Consommation moy.    : {consumption:.2f} L/tour\n"
        f"Tours restants       : {laps_left}\n"
        f"Carburant nécessaire : {needed:.1f} L\n"
        f"Marge                : {margin:+.1f} L\n\n"
        "Un pit stop prend ~22-25s et consomme ~0 L (voiture ralentit). "
        "Analyse et donne ta recommandation."
    ))

    response = await llm.ainvoke([system, user])

    return {
        "messages": [AIMessage(content=response.content, name="fuel_expert")]
    }


# ---------------------------------------------------------------------------
# 3. Team Principal (Supervisor)
# ---------------------------------------------------------------------------

async def team_principal_node(state: TeamState) -> dict:
    """
    Nœud central :
    - Phase routage : décide quel expert consulter ensuite (structured output).
    - Phase finale  : synthétise les rapports et produit la FinalDecision.
    """
    tel       = state["telemetry"]
    messages  = state.get("messages", [])
    consulted = _experts_consulted(messages)
    missing   = [e for e in EXPERTS if e not in consulted]

    # ── Phase routage : il manque encore des experts ──────────────────────
    if missing:
        llm = _get_llm(temperature=0.0).with_structured_output(RoutingDecision)

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
            "messages":      [routing_msg],
            "next_node":     decision.next,
            "final_decision": None,
        }

    # ── Phase finale : tous les experts ont parlé ─────────────────────────
    llm = _get_llm(temperature=0.2).with_structured_output(FinalDecision)

    # Formate les rapports experts
    reports = []
    for msg in messages:
        name = getattr(msg, "name", None)
        if name in EXPERTS:
            label = {"tire_expert": "[TYRE] EXPERT PNEUS", "fuel_expert": "[FUEL] EXPERT CARBURANT"}.get(name, name)
            reports.append(f"{label}:\n{msg.content}")
    expert_reports = "\n\n".join(reports) if reports else "Aucun rapport."

    system_final = SystemMessage(content=(
        "Tu es le Team Principal d'une écurie de course (F1/WEC). "
        "Tu as reçu les analyses de tes experts. "
        "Tu dois synthétiser leurs recommandations et prendre UNE décision finale : "
        "'BOX BOX' (pit stop) ou 'STAY OUT' (rester en piste). "
        "Précise le compound cible et le carburant si tu boxes."
    ))

    user_final = HumanMessage(content=(
        f"=== SITUATION (Tour {tel.get('lap_current')}/{tel.get('lap_total')}) ===\n"
        f"Météo        : {tel.get('weather', tel.get('weather_current', '?'))} | "
        f"Temp. piste  : {tel.get('track_temp_celsius', '?')}°C\n"
        f"Safety Car   : {tel.get('safety_car', False)}\n\n"
        f"=== RAPPORTS EXPERTS ===\n{expert_reports}\n\n"
        "Prends ta décision finale."
    ))

    final: FinalDecision = await llm.ainvoke([system_final, user_final])

    summary_msg = AIMessage(
        content=(
            f"[DÉCISION] {final.action}"
            + (f" → {final.tires}" if final.tires else "")
            + f" | {final.reasoning}"
        ),
        name="team_principal",
    )

    return {
        "messages":      [summary_msg],
        "next_node":     "FINISH",
        "final_decision": final.model_dump(exclude_none=True),
    }
