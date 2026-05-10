"""
Position-bias test on factual statements: FactChecker A2A vs BibOps.

For each statement, the two responses are shown to the gpt-4o judge in
both orderings (FC first, then BibOps; then swapped).  A binomial test
checks whether the judge systematically prefers position A.

Input : data/inputs/benchmark/statements_abtest_bibops.json
Output: data/outputs/benchmark/position_bias_statements_result.json

Usage:
    npx copilot-api@latest start   # Terminal 1
    python scripts/benchmark/test_biais_position_statements.py
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import src.benchmark.ab_test_llm as core

STATEMENTS_PATH = PROJECT_ROOT / "data" / "inputs" / "benchmark" / "statements_abtest_bibops.json"
OUTPUT_PATH = PROJECT_ROOT / "data" / "outputs" / "benchmark" / "position_bias_statements_result.json"


def _binom_pmf(n: int, k: int, p: float) -> float:
    from math import comb
    return comb(n, k) * (p ** k) * ((1 - p) ** (n - k))


def binom_test_two_sided(k: int, n: int, p0: float = 0.5) -> float:
    if n <= 0:
        return 1.0
    p_obs = _binom_pmf(n, k, p0)
    return min(1.0, sum(_binom_pmf(n, i, p0) for i in range(n + 1) if _binom_pmf(n, i, p0) <= p_obs + 1e-15))


def judge_pair(client, statement: str, resp_a: str, resp_b: str) -> tuple[str, str, dict]:
    result = core.evaluer_ticket_par_juge(
        client=client,
        modele_juge=core.DEFAULT_JUDGE_MODEL,
        contexte="",
        question=statement,
        reponse_a=resp_a,
        reponse_b=resp_b,
        modeles_interdits=None,
    )
    if result.get("ok"):
        return result["choix"], result.get("justification", ""), result
    return "?", result.get("erreur", ""), result


def main() -> None:
    client = core.OpenAI(
        api_key="sk-no-key-required",
        base_url=core.COPILOT_BASE_URL,
        timeout=20,
        max_retries=0,
    )

    with open(STATEMENTS_PATH, encoding="utf-8") as f:
        data = json.load(f)

    total = 0
    picks_a = 0
    details = []

    print("\n=== Test de biais de position : BibOps vs FactChecker (statements) ===\n")

    for entry in data:
        statement = entry["statement"]
        fc = entry["factchecker_response"]
        bib = entry["bibops_response"]

        # Ordre 1 : A = FactChecker, B = BibOps
        choix1, justif1, raw1 = judge_pair(client, statement, fc, bib)
        # Ordre 2 : A = BibOps,       B = FactChecker
        choix2, justif2, raw2 = judge_pair(client, statement, bib, fc)

        total += 2
        if choix1 == "A":
            picks_a += 1
        if choix2 == "A":
            picks_a += 1

        details.append({
            "id": entry["id"],
            "statement": statement,
            "A1": fc, "B1": bib, "choix1": choix1, "justif1": justif1, "raw1": raw1,
            "A2": bib, "B2": fc, "choix2": choix2, "justif2": justif2, "raw2": raw2,
        })

        print(f"Affirmation {entry['id']}:")
        print(f"  [A=FactChecker | B=BibOps]    -> Choix: {choix1}")
        print(f"  [A=BibOps      | B=FactChecker] -> Choix: {choix2}")
        time.sleep(2)

    a_rate = picks_a / total if total else 0.0
    p_value = binom_test_two_sided(picks_a, total, 0.5)

    print(f"\nPosition A choisie : {picks_a}/{total} ({a_rate * 100:.1f}%)")
    print(f"p-value binomiale (H0: p=0.5) : {p_value:.6f}")
    print(
        "Interprétation :",
        "Biais de position détecté (p < 0.05)" if p_value < 0.05 else "Pas d'évidence forte de biais de position",
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {
                "summary": {
                    "total": total,
                    "picks_A": picks_a,
                    "A_rate": round(a_rate, 4),
                    "binomial_p": p_value,
                },
                "details": details,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"\nRésultats sauvegardés dans {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
