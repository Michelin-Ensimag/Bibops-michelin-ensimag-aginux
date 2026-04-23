"""
Racing MAS — Demo Script
Simule une situation de course F1 critique et laisse le MAS prendre la décision stratégique.

Prérequis :
  Terminal 1 → npx copilot-api@latest start    (proxy sur localhost:4141)
  Terminal 2 → python -m src.bibops.racing.demo
"""

import sys
import textwrap
import time

from langchain_core.messages import AIMessage, HumanMessage

from src.bibops.racing.graph import compiled_graph
from src.bibops.racing.state import RacingState

# ---------------------------------------------------------------------------
# Couleurs ANSI pour le terminal
# ---------------------------------------------------------------------------

RESET  = "\033[0m"
BOLD   = "\033[1m"
CYAN   = "\033[96m"
YELLOW = "\033[93m"
GREEN  = "\033[92m"
RED    = "\033[91m"
MAGENTA= "\033[95m"
BLUE   = "\033[94m"
GREY   = "\033[90m"

AGENT_COLORS = {
    "supervisor":     MAGENTA,
    "tire_engineer":  YELLOW,
    "fuel_engineer":  CYAN,
    "race_engineer":  BLUE,
}

AGENT_ICONS = {
    "supervisor":    "🎯",
    "tire_engineer": "🔧",
    "fuel_engineer": "⛽",
    "race_engineer": "🏁",
}


# ---------------------------------------------------------------------------
# Scénario de télémétrie — Situation critique tour 45
# ---------------------------------------------------------------------------

TELEMETRY_SCENARIO: dict = {
    # Tour
    "lap_current":       45,
    "lap_total":         70,
    # Météo
    "weather_current":   "Dry",
    "weather_forecast":  "Pluie prévue dans 2 tours (60% probabilité)",
    # Pneus
    "tire_compound":     "Medium",
    "tire_wear_pct":     82.0,        # très usés
    # Carburant
    "fuel_liters":       18.5,
    "fuel_consumption":  1.65,        # L/tour
    # Position & trafic
    "position":          4,
    "gap_ahead_sec":     3.2,         # ~3s derrière P3
    "gap_behind_sec":    8.7,         # ~9s devant P5
    # Perf
    "lap_time_seconds":  91.847,
}


# ---------------------------------------------------------------------------
# Affichage
# ---------------------------------------------------------------------------

def print_banner() -> None:
    print(f"\n{BOLD}{RED}{'═' * 65}{RESET}")
    print(f"{BOLD}{RED}  🏎️  BibOps Racing MAS — Système Multi-Agents Stratégie F1/WEC  🏎️{RESET}")
    print(f"{BOLD}{RED}{'═' * 65}{RESET}\n")


def print_telemetry(tel: dict) -> None:
    laps_left = tel["lap_total"] - tel["lap_current"]
    fuel_needed = laps_left * tel["fuel_consumption"]
    margin = tel["fuel_liters"] - fuel_needed

    print(f"{BOLD}{GREEN}┌─── TÉLÉMÉTRIE ENTRANTE ────────────────────────────────────┐{RESET}")
    print(f"{GREEN}│{RESET}  Tour        : {BOLD}{tel['lap_current']}/{tel['lap_total']}{RESET}  ({laps_left} restants)")
    print(f"{GREEN}│{RESET}  Météo        : {tel['weather_current']}  →  ⚠️  {tel['weather_forecast']}")
    print(f"{GREEN}│{RESET}  Pneus        : {BOLD}{tel['tire_compound']}{RESET} — usure {BOLD}{RED}{tel['tire_wear_pct']}%{RESET}")
    print(f"{GREEN}│{RESET}  Carburant    : {tel['fuel_liters']} L  (besoin {fuel_needed:.1f} L | marge {margin:+.1f} L)")
    print(f"{GREEN}│{RESET}  Position     : P{tel['position']}")
    print(f"{GREEN}│{RESET}  Écart devant : +{tel['gap_ahead_sec']}s  |  Écart derrière : -{tel['gap_behind_sec']}s")
    print(f"{BOLD}{GREEN}└────────────────────────────────────────────────────────────┘{RESET}\n")


def print_step_header(step_num: int) -> None:
    print(f"\n{GREY}{'─' * 65}{RESET}")
    print(f"{GREY}  ⟳ ÉTAPE {step_num}{RESET}")
    print(f"{GREY}{'─' * 65}{RESET}")


def print_agent_message(msg: AIMessage, step: int) -> None:
    name  = getattr(msg, "name", "unknown")
    color = AGENT_COLORS.get(name, RESET)
    icon  = AGENT_ICONS.get(name, "🤖")
    label = name.replace("_", " ").upper()

    print(f"\n{color}{BOLD}{icon}  {label}{RESET}")

    # Indente le contenu pour une meilleure lisibilité
    wrapped = textwrap.fill(
        msg.content,
        width=72,
        initial_indent="   ",
        subsequent_indent="   ",
        break_long_words=False,
    )
    print(wrapped)


def print_final_decision(final_msg: AIMessage) -> None:
    content = final_msg.content
    is_box  = "BOX" in content.upper()
    color   = RED if is_box else GREEN
    symbol  = "🔴" if is_box else "🟢"

    print(f"\n{BOLD}{color}{'═' * 65}{RESET}")
    print(f"{BOLD}{color}  {symbol}  DÉCISION FINALE — RADIO PILOTE{RESET}")
    print(f"{BOLD}{color}{'═' * 65}{RESET}\n")

    for line in content.split("\n"):
        print(f"  {BOLD}{color}{line}{RESET}" if line.strip() else "")

    print(f"\n{BOLD}{color}{'═' * 65}{RESET}\n")


# ---------------------------------------------------------------------------
# Exécution principale
# ---------------------------------------------------------------------------

def run_demo() -> None:
    print_banner()
    print_telemetry(TELEMETRY_SCENARIO)

    # Construire l'état initial
    initial_state: RacingState = {
        "telemetry": TELEMETRY_SCENARIO,
        "messages": [
            HumanMessage(
                content=(
                    f"Tour {TELEMETRY_SCENARIO['lap_current']}/{TELEMETRY_SCENARIO['lap_total']} — "
                    f"Pneus {TELEMETRY_SCENARIO['tire_compound']} à {TELEMETRY_SCENARIO['tire_wear_pct']}% — "
                    f"Météo : pluie imminente. Doit-on s'arrêter ?"
                ),
                name="driver",
            )
        ],
        "next_node": "",
    }

    print(f"{BOLD}🚦 Lancement du système multi-agents...{RESET}\n")
    time.sleep(0.5)

    step = 0
    all_states = []

    # Streaming pas-à-pas via stream()
    for state_update in compiled_graph.stream(initial_state):
        step += 1
        print_step_header(step)

        for node_name, node_output in state_update.items():
            new_msgs = node_output.get("messages", [])
            for msg in new_msgs:
                if isinstance(msg, AIMessage):
                    print_agent_message(msg, step)
                    all_states.append((node_name, msg))

    # La dernière AIMessage du supervisor est la décision finale
    supervisor_msgs = [
        (n, m) for n, m in all_states
        if n == "supervisor" and isinstance(m, AIMessage)
    ]

    if supervisor_msgs:
        _, final = supervisor_msgs[-1]
        if "BOX" in final.content.upper() or "STAY OUT" in final.content.upper():
            print_final_decision(final)

    print(f"{GREY}[MAS terminé en {step} étapes]{RESET}\n")


if __name__ == "__main__":
    try:
        run_demo()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Interruption utilisateur.{RESET}")
        sys.exit(0)
    except Exception as exc:
        print(f"\n{RED}{BOLD}Erreur : {exc}{RESET}")
        print(f"{GREY}Vérifiez que le proxy Copilot tourne sur localhost:4141{RESET}")
        sys.exit(1)
