"""
A/B test: FactChecker A2A vs BibOps on factual statements.

Presents each statement's responses (factchecker / BibOps) to a gpt-4o
judge in randomised order and tallies which model wins more often.

Input : data/inputs/benchmark/statements_abtest_bibops.json
Output: data/outputs/benchmark/ab_llm_statements_result.json

Usage:
    npx copilot-api@latest start   # Terminal 1
    bibops bench ab-test --mode statements
"""
from __future__ import annotations

import json
import random
import re
import time
from pathlib import Path

from openai import OpenAI

from src.common.config import COPILOT_BASE_URL, DEFAULT_JUDGE_MODEL

PROJECT_ROOT = Path(__file__).resolve().parents[3]
INPUT_PATH = PROJECT_ROOT / "data" / "inputs" / "benchmark" / "statements_abtest_bibops.json"
OUTPUT_PATH = PROJECT_ROOT / "data" / "outputs" / "benchmark" / "ab_llm_statements_result.json"
JUDGE_MODEL = DEFAULT_JUDGE_MODEL
RANDOM_SEED = 42

JUDGE_SYSTEM_PROMPT = (
    "Tu es un évaluateur impartial de réponses à des affirmations factuelles. "
    "Pour chaque affirmation, choisis la meilleure réponse entre A et B selon la justesse, "
    "la clarté et la rigueur. "
    "Retourne uniquement un JSON valide avec les clés 'choix' (A ou B) et 'justification'. "
    "Exemple : {\"choix\": \"A\", \"justification\": \"...\"}"
)


def _extract_choice(result: str) -> tuple[str, str]:
    """Return (choice, justification) from the judge's raw text."""
    try:
        candidate = result.strip()
        if not candidate.startswith("{"):
            m = re.search(r"\{[\s\S]*?\}", candidate)
            candidate = m.group(0) if m else "{}"
        parsed = json.loads(candidate)
        for key in ("choix", "best_response", "bestResponse", "meilleure_reponse", "bestAnswer"):
            if key in parsed:
                choix = str(parsed[key]).strip().upper()
                justif = str(parsed.get("justification", ""))
                return choix, justif
    except Exception:
        pass
    return "?", ""


def main() -> None:
    random.seed(RANDOM_SEED)
    client = OpenAI(base_url=COPILOT_BASE_URL, api_key="sk-no-key-required")

    with open(INPUT_PATH, encoding="utf-8") as f:
        data = json.load(f)

    model_a, model_b = "factchecker", "bibops"
    scores = {model_a: 0, model_b: 0}
    results = []

    print(f"\n=== A/B LLM Judge : {model_a} vs {model_b} ===")
    print(f"Juge : {JUDGE_MODEL} | {len(data)} affirmation(s)\n")

    for entry in data:
        statement = entry["statement"]
        resp_fc = entry["factchecker_response"]
        resp_bib = entry["bibops_response"]

        if random.random() < 0.5:
            responses = {"A": resp_fc, "B": resp_bib}
            mapping = {"A": model_a, "B": model_b}
        else:
            responses = {"A": resp_bib, "B": resp_fc}
            mapping = {"A": model_b, "B": model_a}

        prompt = (
            f"Affirmation : {statement}\n\n"
            f"Réponse A :\n{responses['A']}\n\n"
            f"Réponse B :\n{responses['B']}\n\n"
            "Quelle réponse est la meilleure (A ou B) ? Justifie brièvement."
        )

        print(f"--- Affirmation #{entry['id']} ---")
        print(f"{statement}\n")

        try:
            resp = client.chat.completions.create(
                model=JUDGE_MODEL,
                messages=[
                    {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                timeout=60,
            )
            raw_result = resp.choices[0].message.content or ""
        except Exception as exc:
            raw_result = f"[ERROR] {exc}"

        choix, justification = _extract_choice(raw_result)
        winner = mapping.get(choix, "[INDÉTERMINÉ]") if choix in ("A", "B") else "[INDÉTERMINÉ]"
        if winner in scores:
            scores[winner] += 1

        print(f"-> Choix juge: {choix} | Meilleur modèle: {winner}")
        results.append({
            "id": entry["id"],
            "statement": statement,
            "A": responses["A"],
            "B": responses["B"],
            "mapping": mapping,
            "choix": choix,
            "meilleur_modele": winner,
            "justification": justification,
            "judge_result": raw_result,
        })
        time.sleep(2)

    total_votes = sum(scores.values())
    pourcentages = {
        k: round((v / total_votes) * 100, 1) if total_votes else 0.0
        for k, v in scores.items()
    }

    print("\n=== Synthèse des votes ===")
    for modele, score in scores.items():
        print(f"  {modele} : {score} vote(s) ({pourcentages[modele]:.1f}%)")

    payload = {
        "modeles": [model_a, model_b],
        "juge": JUDGE_MODEL,
        "scores": scores,
        "pourcentages": pourcentages,
        "details": results,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\nRésultats sauvegardés dans {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
