"""
BibOps Racing — Arena Launcher
Chef d'orchestre global : lance le Hub et toutes les écuries en parallèle.

Usage :
  python -m src.racing.start_arena

Chaque processus écrit ses logs dans logs/arena/ :
  logs/arena/hub.log
  logs/arena/team_Scuderia_Claude.log
  logs/arena/team_RedBull_GPT.log
  logs/arena/team_McLaren_Ollama.log

Pour suivre une écurie en direct :
  tail -f logs/arena/team_Scuderia_Claude.log
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

# ---------------------------------------------------------------------------
# Configuration de l'arène
# ---------------------------------------------------------------------------

TEAMS = [
    # (nom_écurie,    modèle_llm)
    # Seuls les modèles GPT sont acceptés par le backend GitHub Copilot.
    # Les modèles Claude (claude-sonnet-4.6, etc.) sont listés par le proxy
    # mais retournent 400 model_not_supported au moment des completions.
    ("Ferrari_Pro",   "gpt-4o"),
    ("RedBull_Fast",  "gpt-4o-mini"),
    ("McLaren_New",   "gpt-4.1"),
]

HUB_STARTUP_WAIT = 4   # secondes avant de lancer les écuries
TEAM_STAGGER     = 0.3  # secondes entre chaque lancement d'écurie

LOG_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "logs", "arena"
)

# ---------------------------------------------------------------------------
# Couleurs ANSI
# ---------------------------------------------------------------------------

RESET  = "\033[0m"
BOLD   = "\033[1m"
CYAN   = "\033[96m"
YELLOW = "\033[93m"
GREEN  = "\033[92m"
RED    = "\033[91m"
GREY   = "\033[90m"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _banner() -> None:
    print(f"\n{BOLD}{CYAN}{'╔' + '═' * 58 + '╗'}{RESET}")
    print(f"{BOLD}{CYAN}║{'BibOps Racing — Distributed AI Arena':^58}║{RESET}")
    print(f"{BOLD}{CYAN}{'╚' + '═' * 58 + '╝'}{RESET}\n")


def _ensure_log_dir() -> None:
    os.makedirs(LOG_DIR, exist_ok=True)


def _log_path(name: str) -> str:
    return os.path.join(LOG_DIR, f"{name}.log")


def _open_log(name: str):
    path = _log_path(name)
    return open(path, "w", encoding="utf-8", buffering=1)   # line-buffered


def _launch(cmd: list[str], log_name: str) -> tuple[subprocess.Popen, str]:
    """Lance un sous-processus avec redirection des logs."""
    log_file = _open_log(log_name)
    proc = subprocess.Popen(
        cmd,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        # Pas de shell=True pour le Ctrl+C propre
    )
    return proc, _log_path(log_name)


def _terminate_all(procs: list[tuple[str, subprocess.Popen]]) -> None:
    print(f"\n{YELLOW}⛔  Arrêt de l'arène...{RESET}")
    for name, proc in procs:
        if proc.poll() is None:          # encore vivant
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
            print(f"  {GREY}→ {name} arrêté{RESET}")


# ---------------------------------------------------------------------------
# Lanceur principal
# ---------------------------------------------------------------------------

def main() -> None:
    _banner()
    _ensure_log_dir()

    procs: list[tuple[str, subprocess.Popen]] = []
    python = sys.executable

    # ── 1. Hub ──────────────────────────────────────────────────────────
    print(f"{BOLD}[1/4] Démarrage du Hub...{RESET}")
    hub_cmd = [python, "-m", "src.racing.hub.server"]
    hub_proc, hub_log = _launch(hub_cmd, "hub")
    procs.append(("Hub", hub_proc))
    print(f"  {GREEN}✓ Hub lancé{RESET}  PID={hub_proc.pid}  "
          f"{GREY}→ {hub_log}{RESET}")

    # ── 2. Attente du démarrage du Hub ──────────────────────────────────
    print(f"\n{BOLD}[2/4] Attente du Hub ({HUB_STARTUP_WAIT}s)...{RESET}")
    for i in range(HUB_STARTUP_WAIT, 0, -1):
        print(f"  {GREY}{i}s...{RESET}", end="\r", flush=True)
        time.sleep(1)
    print()

    # ── 3. Écuries ──────────────────────────────────────────────────────
    print(f"{BOLD}[3/4] Lancement des écuries...{RESET}\n")
    for team, model in TEAMS:
        team_cmd = [
            python, "-m", "src.racing.team_client.main",
            "--team", team,
            "--model", model,
        ]
        proc, log = _launch(team_cmd, f"team_{team}")
        procs.append((team, proc))
        print(f"  {GREEN}✓{RESET} {BOLD}{team:<22}{RESET}  "
              f"modèle={CYAN}{model}{RESET}  "
              f"PID={proc.pid}  {GREY}→ {log}{RESET}")
        time.sleep(TEAM_STAGGER)

    # ── 4. Tableau de bord ──────────────────────────────────────────────
    print(f"\n{BOLD}[4/4] Arène lancée ! 🏁{RESET}\n")
    print(f"{BOLD}{'─' * 58}{RESET}")
    print(f"  Résultats en direct  : {CYAN}curl http://localhost:8000/results{RESET}")
    print(f"  Snapshot course      : {CYAN}curl http://localhost:8000/status{RESET}")
    print(f"\n  Suivre une écurie :")
    for team, _ in TEAMS:
        print(f"    {GREY}tail -f {_log_path(f'team_{team}')}{RESET}")
    print(f"\n  {YELLOW}Ctrl+C pour arrêter toute l'arène.{RESET}")
    print(f"{'─' * 58}\n")

    # ── Surveillance ────────────────────────────────────────────────────
    try:
        while True:
            # Vérifie si tous les processus sont terminés
            alive = [(n, p) for n, p in procs if p.poll() is None]
            if not alive:
                print(f"\n{GREEN}{BOLD}Tous les processus sont terminés.{RESET}")
                break
            time.sleep(2)

    except KeyboardInterrupt:
        _terminate_all(procs)
        sys.exit(0)


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()
