"""
Racing MAS — Shared State
TypedDict unique traversant tout le graphe LangGraph.
"""

import operator
from typing import Annotated, List, TypedDict

from langchain_core.messages import BaseMessage


class RacingState(TypedDict):
    """
    État global partagé entre tous les nœuds du graphe de stratégie.

    telemetry : snapshot temps-réel de la course.
    messages  : historique des échanges entre agents (append-only via operator.add).
    next_node : décision du Supervisor — quel expert appeler ensuite, ou 'FINISH'.
    """

    telemetry: dict
    """
    Clés attendues :
      lap_current      (int)   — tour actuel
      lap_total        (int)   — nombre total de tours
      weather_current  (str)   — "Dry" | "Wet" | "Intermediate"
      weather_forecast (str)   — description météo à venir
      tire_compound    (str)   — "Soft" | "Medium" | "Hard" | "Intermediate" | "Wet"
      tire_wear_pct    (float) — usure en %, 0 = neuf, 100 = mort
      fuel_liters      (float) — litres d'essence restants
      fuel_consumption (float) — consommation moyenne L/tour
      position         (int)   — position en course
      gap_ahead_sec    (float) — écart avec la voiture devant (secondes)
      gap_behind_sec   (float) — écart avec la voiture derrière (secondes)
      lap_time_seconds (float) — meilleur temps au tour récent
    """

    messages: Annotated[List[BaseMessage], operator.add]
    """
    Historique complet des messages échangés entre agents.
    L'annotation operator.add garantit l'accumulation sans écrasement.
    """

    next_node: str
    """
    Prochain nœud ciblé par le Supervisor :
      "tire_engineer" | "fuel_engineer" | "race_engineer" | "FINISH"
    """
