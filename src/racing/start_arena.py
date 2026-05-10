"""
BibOps Racing — Adversarial Arena Launcher
Chef d'orchestre global : lance le Hub et les 4 écuries en parallèle.

Usage :
  python -m src.racing.start_arena

Chaque processus écrit ses logs dans logs/arena/ :
  logs/arena/hub.log
  logs/arena/team_team_a_zero_shot.log
  logs/arena/team_team_b_react.log
  logs/arena/team_team_c_validated.log
  logs/arena/team_team_psi.log

Pour suivre une écurie en direct :
  tail -f logs/arena/team_team_psi.log

Rapport de sécurité après la course :
  data/outputs/benchmark/security_race_report.json
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

import httpx

# ---------------------------------------------------------------------------
# Configuration de l'arène adversariale
# ---------------------------------------------------------------------------
#
# (nom_écurie, module_python, modèle_llm, query_port)
#   team_a_zero_shot  — zero-shot, HIGH vulnerability
#   team_b_react      — ReAct + tools, MEDIUM vulnerability  (existing team_client)
#   team_c_validated  — validator gate, LOW vulnerability
#   team_psi          — adversarial attacker

TEAMS = [
    ("team_a_zero_shot", "src.racing.team_zero_shot.main",  "gpt-4.1", 8011),
    ("team_b_react",     "src.racing.team_client.main",     "gpt-4.1", 8012),
    ("team_c_validated", "src.racing.team_validated.main",  "gpt-4.1", 8013),
    ("team_psi",         "src.racing.team_psi.main",        "gpt-4o",  8014),
]

HUB_STARTUP_WAIT = 5   # secondes avant de lancer les écuries
TEAM_STAGGER     = 0.5  # secondes entre chaque lancement d'écurie

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
    print(f"{BOLD}[3/4] Lancement des écuries adversariales...{RESET}\n")
    for team, module, model, query_port in TEAMS:
        team_cmd = [
            python, "-m", module,
            "--team",       team,
            "--model",      model,
            "--query-port", str(query_port),
        ]
        proc, log = _launch(team_cmd, f"team_{team}")
        procs.append((team, proc))
        vuln = {"team_a_zero_shot": "HIGH", "team_b_react": "MED", "team_c_validated": "LOW", "team_psi": "ATTACKER"}.get(team, "?")
        print(f"  {GREEN}✓{RESET} {BOLD}{team:<22}{RESET}  "
              f"model={CYAN}{model}{RESET}  "
              f"port={query_port}  vuln={YELLOW}{vuln}{RESET}  "
              f"PID={proc.pid}  {GREY}→ {log}{RESET}")
        time.sleep(TEAM_STAGGER)

    # ── 4. Tableau de bord ──────────────────────────────────────────────
    print(f"\n{BOLD}[4/4] Arène adversariale lancée !{RESET}\n")
    print(f"{BOLD}{'─' * 64}{RESET}")
    print(f"  Résultats course     : {CYAN}curl http://localhost:8000/results{RESET}")
    print(f"  Snapshot course      : {CYAN}curl http://localhost:8000/status{RESET}")
    print(f"  Stratégie d'écurie   : {CYAN}curl http://localhost:8000/team/team_a_zero_shot/strategy{RESET}")
    print(f"  Historique complet   : {CYAN}curl http://localhost:8000/race-history{RESET}")
    print(f"\n  Suivre une écurie :")
    for team, _, _, _ in TEAMS:
        print(f"    {GREY}tail -f {_log_path(f'team_{team}')}{RESET}")
    print(f"\n  {YELLOW}Ctrl+C pour arrêter toute l'arène.{RESET}")
    print(f"{'─' * 64}\n")

    # ── Surveillance ────────────────────────────────────────────────────
    try:
        while True:
            alive = [(n, p) for n, p in procs if p.poll() is None]
            if not alive:
                print(f"\n{GREEN}{BOLD}Tous les processus sont terminés.{RESET}")
                _generate_security_report()
                break
            time.sleep(2)

    except KeyboardInterrupt:
        _terminate_all(procs)
        _generate_security_report()
        sys.exit(0)


def _generate_security_report() -> None:
    """Ask the hub ObserverEngine to finalize and write the security report."""
    print(f"\n{BOLD}Génération du rapport de sécurité...{RESET}")
    try:
        resp = httpx.post("http://localhost:8000/observer/finalize", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            print(f"{GREEN}Rapport généré — extractions Team Psi : {data.get('extractions', 0)}{RESET}")
            print(f"{GREY}→ data/outputs/benchmark/security_race_report.json{RESET}")
        else:
            print(f"{RED}Impossible de générer le rapport (hub déjà arrêté ?){RESET}")
    except Exception as exc:
        print(f"{RED}Rapport non généré : {exc}{RESET}")


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()
