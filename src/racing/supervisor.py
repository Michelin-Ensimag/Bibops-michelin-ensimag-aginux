"""
Racing MAS — Supervisor Node
Orchestrateur LLM qui coordonne les experts via Function Calling (structured output).
Il collecte les avis, puis rend la décision finale au pilote.
"""

from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from .state import RacingState

# ---------------------------------------------------------------------------
# Schéma de routage (structured output via function calling)
# ---------------------------------------------------------------------------

EXPERTS = ["tire_engineer", "fuel_engineer", "race_engineer"]


class RoutingDecision(BaseModel):
    """Décision de routage du Supervisor vers le prochain nœud du graphe."""

    next: Literal["tire_engineer", "fuel_engineer", "race_engineer", "FINISH"] = Field(
        description=(
            "Prochain expert à consulter, ou 'FINISH' si tous les avis nécessaires "
            "ont été recueillis pour prendre la décision finale."
        )
    )
    reasoning: str = Field(
        description="Justification courte (1-2 phrases) du choix de routage."
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_llm(temperature: float = 0.1) -> ChatOpenAI:
    return ChatOpenAI(
        model="gpt-4o",
        base_url="http://localhost:4141/v1",
        api_key="copilot",
        temperature=temperature,
        max_tokens=1024,
    )


def _experts_already_consulted(messages) -> list[str]:
    """Retourne la liste des experts ayant déjà répondu dans l'historique."""
    consulted = []
    for msg in messages:
        if hasattr(msg, "name") and msg.name in EXPERTS and msg.name not in consulted:
            consulted.append(msg.name)
    return consulted


def _format_expert_reports(messages) -> str:
    """Formate les rapports experts pour le prompt final du Supervisor."""
    reports = []
    for msg in messages:
        if hasattr(msg, "name") and msg.name in EXPERTS:
            label = {
                "tire_engineer": "[TYRE] INGÉNIEUR PNEUS",
                "fuel_engineer": "[FUEL] INGÉNIEUR CARBURANT",
                "race_engineer": "[RACE] INGÉNIEUR DE COURSE",
            }.get(msg.name, msg.name.upper())
            reports.append(f"{label}:\n{msg.content}")
    return "\n\n".join(reports) if reports else "Aucun rapport expert disponible."


# ---------------------------------------------------------------------------
# Supervisor Node
# ---------------------------------------------------------------------------

def supervisor_node(state: RacingState) -> dict:
    """
    Nœud Supervisor :
    1. Si des experts manquent → utilise structured output pour décider qui appeler.
    2. Si tous les experts ont répondu → génère la décision finale BOX BOX / STAY OUT.
    """
    tel = state["telemetry"]
    messages = state.get("messages", [])
    consulted = _experts_already_consulted(messages)
    missing = [e for e in EXPERTS if e not in consulted]

    # ---- Phase de routage : il manque encore des experts ----
    if missing:
        llm = _get_llm(temperature=0.0)
        structured_llm = llm.with_structured_output(RoutingDecision)

        consulted_str = ", ".join(consulted) if consulted else "aucun"
        missing_str = ", ".join(missing)

        system = SystemMessage(content=(
            "Tu es le Directeur Stratégique d'une écurie de F1/WEC. "
            "Tu coordonnes une équipe d'experts pour décider si la voiture doit s'arrêter aux stands. "
            "Tu dois consulter les trois experts (tire_engineer, fuel_engineer, race_engineer) "
            "avant de rendre ta décision finale. "
            "Choisis le prochain expert le plus pertinent à consulter en fonction de la situation."
        ))

        user_msg = HumanMessage(content=(
            f"Tour {tel.get('lap_current')}/{tel.get('lap_total')} | "
            f"P{tel.get('position')} | "
            f"Pneus {tel.get('tire_compound')} à {tel.get('tire_wear_pct')}% | "
            f"Météo : {tel.get('weather_current')} → {tel.get('weather_forecast')}\n\n"
            f"Experts déjà consultés : {consulted_str}\n"
            f"Experts restants       : {missing_str}\n\n"
            "Qui dois-je consulter maintenant ?"
        ))

        decision: RoutingDecision = structured_llm.invoke([system, user_msg])

        routing_msg = AIMessage(
            content=f"[Supervisor → {decision.next}] {decision.reasoning}",
            name="supervisor",
        )

        return {
            "messages": [routing_msg],
            "next_node": decision.next,
        }

    # ---- Phase finale : tous les experts ont parlé ----
    llm = _get_llm(temperature=0.3)
    expert_reports = _format_expert_reports(messages)

    system_final = SystemMessage(content=(
        "Tu es le Directeur Stratégique d'une écurie de F1/WEC. "
        "Tu as reçu les analyses de tes trois experts. "
        "Tu dois maintenant synthétiser leurs recommandations et rendre UNE décision finale, "
        "claire et autoritaire, au pilote sur sa radio de bord. "
        "Commence toujours par '[BOX] BOX BOX BOX' ou '[GO] STAY OUT STAY OUT' en majuscules. "
        "Ensuite explique brièvement la stratégie (compound si pit, timing, raison). "
        "Sois direct — c'est une communication radio en course."
    ))

    user_final = HumanMessage(content=(
        f"=== SITUATION (Tour {tel.get('lap_current')}/{tel.get('lap_total')}) ===\n"
        f"Position : P{tel.get('position')} | Pneus : {tel.get('tire_compound')} "
        f"({tel.get('tire_wear_pct')}% usure) | Carburant : {tel.get('fuel_liters')} L\n"
        f"Météo : {tel.get('weather_current')} → {tel.get('weather_forecast')}\n\n"
        f"=== RAPPORTS EXPERTS ===\n{expert_reports}\n\n"
        "Rends ta décision finale au pilote."
    ))

    final_response = llm.invoke([system_final, user_final])

    final_msg = AIMessage(
        content=final_response.content,
        name="supervisor",
    )

    return {
        "messages": [final_msg],
        "next_node": "FINISH",
    }
