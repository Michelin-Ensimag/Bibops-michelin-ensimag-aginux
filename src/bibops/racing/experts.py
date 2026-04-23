"""
Racing MAS — Expert Nodes
Trois ingénieurs spécialisés, chacun analysant un aspect critique de la stratégie.
Chaque nœud reçoit le RacingState complet et retourne un dict de mise à jour.
"""

from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI


# ---------------------------------------------------------------------------
# LLM partagé (proxy Copilot local)
# ---------------------------------------------------------------------------

def _get_llm(temperature: float = 0.2) -> ChatOpenAI:
    return ChatOpenAI(
        model="gpt-4o",
        base_url="http://localhost:4141/v1",
        api_key="copilot",          # dummy key — proxy n'authentifie pas
        temperature=temperature,
        max_tokens=512,
    )


# ---------------------------------------------------------------------------
# 1. Ingénieur pneus
# ---------------------------------------------------------------------------

def tire_engineer_node(state: dict) -> dict:
    """
    Analyse la dégradation des pneus et la météo.
    Recommande : GARDER ou CHANGER (et vers quel compound).
    """
    tel = state["telemetry"]
    llm = _get_llm(temperature=0.1)

    system = SystemMessage(content=(
        "Tu es l'Ingénieur Pneus d'une écurie de F1/WEC. "
        "Tu analyses uniquement les données pneus et météo pour formuler une recommandation claire et chiffrée. "
        "Sois concis et précis. Termine toujours par : RECOMMANDATION PNEUS : [GARDER / CHANGER → compound]."
    ))

    user_prompt = (
        f"=== TÉLÉMÉTRIE PNEUS & MÉTÉO (Tour {tel.get('lap_current')}/{tel.get('lap_total')}) ===\n"
        f"Compound actuel   : {tel.get('tire_compound')}\n"
        f"Usure             : {tel.get('tire_wear_pct')}%\n"
        f"Météo actuelle    : {tel.get('weather_current')}\n"
        f"Météo prévue      : {tel.get('weather_forecast')}\n"
        f"Tours restants    : {tel.get('lap_total', 0) - tel.get('lap_current', 0)}\n\n"
        "Analyse et donne ta recommandation."
    )

    response = llm.invoke([system, HumanMessage(content=user_prompt)])

    return {
        "messages": [
            AIMessage(
                content=response.content,
                name="tire_engineer",
            )
        ]
    }


# ---------------------------------------------------------------------------
# 2. Ingénieur carburant
# ---------------------------------------------------------------------------

def fuel_engineer_node(state: dict) -> dict:
    """
    Calcule si le carburant restant est suffisant pour finir la course.
    Évalue également l'impact d'un arrêt sur la consommation.
    """
    tel = state["telemetry"]
    llm = _get_llm(temperature=0.1)

    laps_remaining = tel.get("lap_total", 0) - tel.get("lap_current", 0)
    fuel = tel.get("fuel_liters", 0.0)
    consumption = tel.get("fuel_consumption", 1.8)
    fuel_needed = laps_remaining * consumption
    margin = fuel - fuel_needed

    system = SystemMessage(content=(
        "Tu es l'Ingénieur Carburant d'une écurie de F1/WEC. "
        "Tu analyses uniquement le budget carburant. "
        "Sois précis et quantifié. Termine toujours par : RECOMMANDATION CARBURANT : [SUFFISANT / CRITIQUE / MAPPING REQUIS]."
    ))

    user_prompt = (
        f"=== TÉLÉMÉTRIE CARBURANT (Tour {tel.get('lap_current')}/{tel.get('lap_total')}) ===\n"
        f"Carburant restant   : {fuel:.1f} L\n"
        f"Consommation moy.   : {consumption:.2f} L/tour\n"
        f"Tours restants      : {laps_remaining}\n"
        f"Carburant nécessaire: {fuel_needed:.1f} L\n"
        f"Marge               : {margin:+.1f} L\n\n"
        "Un arrêt aux stands fait perdre ~25s et consomme ~0 L (voiture ralentit). "
        "Analyse la situation et donne ta recommandation."
    )

    response = llm.invoke([system, HumanMessage(content=user_prompt)])

    return {
        "messages": [
            AIMessage(
                content=response.content,
                name="fuel_engineer",
            )
        ]
    }


# ---------------------------------------------------------------------------
# 3. Ingénieur de course (trafic & stratégie)
# ---------------------------------------------------------------------------

def race_engineer_node(state: dict) -> dict:
    """
    Analyse le trafic, les écarts avec les adversaires.
    Évalue le risque d'undercut / overcut et l'impact d'un pit sur la position.
    """
    tel = state["telemetry"]
    llm = _get_llm(temperature=0.3)

    system = SystemMessage(content=(
        "Tu es l'Ingénieur de Course (Race Engineer) d'une écurie de F1/WEC. "
        "Tu analyses les écarts avec les adversaires pour évaluer l'opportunité stratégique d'un arrêt. "
        "Considère le risque d'undercut (adversaire derrière qui s'arrête en premier) et d'overcut (rester en piste plus longtemps). "
        "Termine toujours par : RECOMMANDATION STRATÉGIE : [UNDERCUT RISQUÉ / OVERCUT POSSIBLE / PIT SAFE / STAY OUT]."
    ))

    user_prompt = (
        f"=== TÉLÉMÉTRIE COURSE (Tour {tel.get('lap_current')}/{tel.get('lap_total')}) ===\n"
        f"Position actuelle   : P{tel.get('position')}\n"
        f"Écart devant        : +{tel.get('gap_ahead_sec', 0):.2f}s\n"
        f"Écart derrière      : -{tel.get('gap_behind_sec', 0):.2f}s\n"
        f"Meilleur tour récent: {tel.get('lap_time_seconds', 90.0):.3f}s\n"
        f"Compound actuel     : {tel.get('tire_compound')} ({tel.get('tire_wear_pct')}% usure)\n\n"
        "Un pit stop prend ~22-25s. Analyse si un arrêt serait safe ou si l'on risque de ressortir dans le trafic."
    )

    response = llm.invoke([system, HumanMessage(content=user_prompt)])

    return {
        "messages": [
            AIMessage(
                content=response.content,
                name="race_engineer",
            )
        ]
    }
