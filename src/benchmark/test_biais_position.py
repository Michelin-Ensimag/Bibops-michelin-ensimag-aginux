"""
Test de biais de position avec juge LLM.

Principe:
- Pour chaque ticket, on génère une réponse du modèle A et du modèle B.
- On évalue 2 fois le même contenu:
  1) ordre normal   : A=réponse_A, B=réponse_B
  2) ordre inversé  : A=réponse_B, B=réponse_A

Usage (PowerShell):
    npx copilot-api@latest start
    python src/bibops/benchmark/test-biais-position.py

Exemple:
    python src/bibops/benchmark/test-biais-position.py --max-tickets 40 --model-a gpt-4o-mini --model-b claude-haiku-4.5 --judge-model gpt-4o
"""

import argparse
import csv
import json
import math
import os
import random
import sys
from pathlib import Path
from typing import Dict, Any

from openai import OpenAI

# Permet l'import de `src.*` meme si le script est lance par chemin absolu.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.benchmark import ab_test_llm as core


OUTPUT_JSON = os.path.join(core.BASE_DIR, "data", "outputs", "benchmark", "position_bias_resultat.json")
DEFAULT_MAX_TICKETS = int(os.environ.get("BIBOPS_POSITION_MAX_TICKETS", "2"))


def _binom_pmf(n: int, k: int, p: float) -> float:
    return math.comb(n, k) * (p ** k) * ((1 - p) ** (n - k))


def binom_test_two_sided(k: int, n: int, p0: float = 0.5) -> float:
    """Exact two-sided binomial test p-value (no scipy dependency)."""
    if n <= 0:
        return 1.0

    p_obs = _binom_pmf(n, k, p0)
    p_value = 0.0
    for i in range(n + 1):
        p_i = _binom_pmf(n, i, p0)
        if p_i <= p_obs + 1e-15:
            p_value += p_i
    return min(1.0, p_value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Test de biais de position (A/B) du juge LLM")
    parser.add_argument("--model-a", default=core.DEFAULT_MODEL_A, help="Premier modèle candidat")
    parser.add_argument("--model-b", default=core.DEFAULT_MODEL_B, help="Deuxième modèle candidat")
    parser.add_argument("--judge-model", default=core.DEFAULT_JUDGE_MODEL, help="Modèle juge")
    parser.add_argument("--max-tickets", type=int, default=DEFAULT_MAX_TICKETS, help="Nombre max de tickets à analyser")
    parser.add_argument("--seed", type=int, default=42, help="Graine aléatoire")
    parser.add_argument("--output", default=OUTPUT_JSON, help="Chemin du JSON de sortie")
    args = parser.parse_args()

    api_key = core.charger_copilot_api_key()
    client = OpenAI(api_key=api_key, base_url=core.COPILOT_BASE_URL, timeout=20, max_retries=0)

    rng = random.Random(args.seed)

    with open(core.INPUT_CSV, newline="", encoding="utf-8") as f:
        tickets = list(csv.DictReader(f))
    if args.max_tickets > 0:
        tickets = tickets[: args.max_tickets]

    total_judgments = 0
    picks_a_position = 0
    valid_pairs = 0

    details = []

    print(f"\n=== Test biais de position : {args.model_a} vs {args.model_b} | juge={args.judge_model} ===")
    print(f"{len(tickets)} ticket(s)\n")

    for ticket in tickets:
        tid = ticket["id"]
        contexte = ticket["contexte"]
        question = ticket["ticket"]

        print(f"--- Ticket #{tid} ---")

        rep_a, model_a_eff, _ = core.generer_reponse_avec_fallback(
            client,
            args.model_a,
            contexte,
            question,
            modeles_interdits={args.judge_model},
            etiquette="A",
        )
        rep_b, model_b_eff, _ = core.generer_reponse_avec_fallback(
            client,
            args.model_b,
            contexte,
            question,
            modeles_interdits={model_a_eff, args.judge_model},
            etiquette="B",
        )

        if core._est_reponse_erreur(rep_a) or core._est_reponse_erreur(rep_b):
            details.append(
                {
                    "ticket_id": tid,
                    "status": "candidate_error",
                    "model_a_effectif": model_a_eff,
                    "model_b_effectif": model_b_eff,
                    "error_a": rep_a if core._est_reponse_erreur(rep_a) else "",
                    "error_b": rep_b if core._est_reponse_erreur(rep_b) else "",
                }
            )
            continue

        # Ordre normal
        j1 = core.evaluer_ticket_par_juge(
            client=client,
            modele_juge=args.judge_model,
            contexte=contexte,
            question=question,
            reponse_a=rep_a,
            reponse_b=rep_b,
            modeles_interdits={model_a_eff, model_b_eff},
        )

        # Ordre inversé
        j2 = core.evaluer_ticket_par_juge(
            client=client,
            modele_juge=args.judge_model,
            contexte=contexte,
            question=question,
            reponse_a=rep_b,
            reponse_b=rep_a,
            modeles_interdits={model_a_eff, model_b_eff},
        )

        item: Dict[str, Any] = {
            "ticket_id": tid,
            "question": question,
            "model_a_effectif": model_a_eff,
            "model_b_effectif": model_b_eff,
            "jugement_normal": j1,
            "jugement_inverse": j2,
            "status": "ok",
        }

        ok1 = j1.get("ok", False)
        ok2 = j2.get("ok", False)

        if ok1:
            total_judgments += 1
            if j1.get("choix") == "A":
                picks_a_position += 1
        if ok2:
            total_judgments += 1
            if j2.get("choix") == "A":
                picks_a_position += 1

        if ok1 and ok2:
            valid_pairs += 1

        if not (ok1 and ok2):
            item["status"] = "judge_partial_error"

        details.append(item)

        # Anti-burst: petit jitter pour limiter les 429 en campagne longue
        if rng.random() < 0.35:
            pass

    p_value = binom_test_two_sided(picks_a_position, total_judgments, 0.5)
    a_rate = (picks_a_position / total_judgments) if total_judgments else 0.0

    summary = {
        "models": {"A": args.model_a, "B": args.model_b, "judge": args.judge_model},
        "tickets_total": len(tickets),
        "valid_pairs": valid_pairs,
        "total_judgments": total_judgments,
        "picks_A_position": picks_a_position,
        "picks_B_position": max(0, total_judgments - picks_a_position),
        "A_position_rate": round(a_rate, 4),
        "binomial_test_two_sided_pvalue": p_value,
        "interpretation": (
            "Evidence de biais de position" if (total_judgments > 0 and p_value < 0.05) else "Pas d'evidence statistique forte de biais de position"
        ),
    }

    payload = {"summary": summary, "details": details}

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("\n=== Résumé biais de position ===")
    print(f"Jugements valides: {total_judgments}")
    print(f"Choix position A: {picks_a_position} ({a_rate * 100:.1f}%)")
    print(f"p-value binomiale (H0: p=0.5): {p_value:.6f}")
    print(f"Interprétation: {summary['interpretation']}")
    print(f"\nRésultats sauvegardés dans {args.output}")


if __name__ == "__main__":
    main()
