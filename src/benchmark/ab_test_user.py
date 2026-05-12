"""
Test A/B humain : compare deux modeles Copilot API en aveugle.

Usage (PowerShell):
    npx copilot-api@latest start
    python src/bibops/benchmark/ab_test_user.py
    python src/bibops/benchmark/ab_test_user.py --model-a gpt-4o-mini --model-b claude-haiku-4.5

Le script lit les tickets depuis tickets_scenario_1.csv, genere une reponse
par modele, les presente en aveugle (A/B) a l'evaluateur humain, enregistre
son choix, et sauvegarde les resultats dans ab_user_resultat.json.
"""

import argparse
import csv
import json
import os
import random
import time
import sys

from openai import OpenAI

from src.common.config import COPILOT_BASE_URL
from src.common.text import _extraire_texte, charger_copilot_api_key

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
INPUT_CSV = os.path.join(BASE_DIR, "data", "inputs", "benchmark", "tickets_scenario_1.csv")
OUTPUT_JSON = os.path.join(BASE_DIR, "data", "outputs", "benchmark", "ab_user_resultat.json")

DEFAULT_MODEL_A = "gpt-4o-mini"
DEFAULT_MODEL_B = "claude-haiku-4.5"
MAX_TICKETS = 10


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
        return value if value > 0 else default
    except ValueError:
        return default


def _auto_choice_default() -> str:
    raw = os.environ.get("BIBOPS_AB_USER_CHOICE", "A").strip().upper()
    return raw if raw in ("A", "B") else "A"


def _is_non_interactive_mode() -> bool:
    return os.environ.get("BIBOPS_NON_INTERACTIVE", "0") == "1" or not sys.stdin.isatty()


def appeler_modele(client: OpenAI, modele: str, contexte: str, ticket: str, retries: int) -> str:
    last_error = ""
    for attempt in range(1, retries + 1):
        try:
            reponse = client.chat.completions.create(
                model=modele,
                messages=[
                    {"role": "system", "content": contexte},
                    {"role": "user", "content": ticket},
                ],
                max_tokens=512,
                temperature=0,
            )
            return _extraire_texte(reponse.choices[0].message)
        except Exception as exc:
            last_error = str(exc)
            if attempt < retries:
                time.sleep(1.2 * attempt)

    return f"[ERREUR_MODELE {modele}] {last_error}"


def main():
    parser = argparse.ArgumentParser(description="Test A/B humain entre deux modeles Copilot API")
    parser.add_argument("--model-a", default=DEFAULT_MODEL_A, help="Premier modele")
    parser.add_argument("--model-b", default=DEFAULT_MODEL_B, help="Deuxieme modele")
    parser.add_argument("--seed", type=int, default=42, help="Graine aléatoire pour l'ordre A/B")
    parser.add_argument("--retries", type=int, default=3, help="Nombre de tentatives API par appel")
    parser.add_argument("--max-tickets", type=int, default=_env_int("BIBOPS_AB_USER_MAX_TICKETS", MAX_TICKETS), help="Nombre max de tickets")
    parser.add_argument("--auto-choice", choices=["A", "B"], default=_auto_choice_default(), help="Choix auto en mode non interactif")
    args = parser.parse_args()

    api_key = charger_copilot_api_key()
    client = OpenAI(api_key=api_key, base_url=COPILOT_BASE_URL, timeout=40)

    rng = random.Random(args.seed)

    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        tickets = list(csv.DictReader(f))[:args.max_tickets]

    resultats = []
    scores = {args.model_a: 0, args.model_b: 0}

    print(f"\n=== Evaluation A/B : {args.model_a} vs {args.model_b} ===")
    print(f"{len(tickets)} ticket(s) à évaluer.\n")

    for ticket in tickets:
        tid = ticket["id"]
        contexte = ticket["contexte"]
        question = ticket["ticket"]

        print(f"--- Ticket #{tid} ---")
        print(f"Question : {question}\n")
        print("Génération des réponses en cours...")

        rep_a_modele = appeler_modele(client, args.model_a, contexte, question, args.retries)
        rep_b_modele = appeler_modele(client, args.model_b, contexte, question, args.retries)

        # Mélange aléatoire : le correcteur ne sait pas quel modèle est A ou B
        if rng.random() < 0.5:
            label_a, rep_a = args.model_a, rep_a_modele
            label_b, rep_b = args.model_b, rep_b_modele
        else:
            label_a, rep_a = args.model_b, rep_b_modele
            label_b, rep_b = args.model_a, rep_a_modele

        print(f"\n--- Réponse A ---\n{rep_a}\n")
        print(f"--- Réponse B ---\n{rep_b}\n")

        if _is_non_interactive_mode():
            choix = args.auto_choice
            print(f"[Mode non interactif] choix automatique: {choix}")
        else:
            while True:
                try:
                    choix = input("Quelle réponse est meilleure ? (A/B) : ").strip().upper()
                except EOFError:
                    choix = args.auto_choice
                    print(f"\n[EOF] choix automatique: {choix}")
                if choix in ("A", "B"):
                    break
                print("Répondez A ou B.")

        meilleur_modele = label_a if choix == "A" else label_b
        scores[meilleur_modele] += 1

        resultats.append({
            "ticket_id": tid,
            "question": question,
            "reponse_a": rep_a,
            "reponse_b": rep_b,
            "choix_humain": choix,
            "meilleur_modele": meilleur_modele,
        })

        print(f"→ Meilleur modele (selon l'evaluateur) : {meilleur_modele}\n")

    print("=== Synthese des votes ===")
    total_votes = sum(scores.values())
    pourcentages = {}
    for modele, score in scores.items():
        pct = round((score / total_votes) * 100, 1) if total_votes else 0.0
        pourcentages[modele] = pct
        print(f"  {modele} : {score} vote(s) ({pct:.1f}%)")

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(
            {
                "modeles": [args.model_a, args.model_b],
                "scores": scores,
                "pourcentages": pourcentages,
                "details": resultats,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"\nRésultats sauvegardés dans {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
