"""
Test A/B humain : compare deux modeles OpenRouter en aveugle.

Usage (PowerShell):
    $env:OPENROUTER_API_KEY = [Environment]::GetEnvironmentVariable("OPENROUTER_API_KEY", "User")
    python src/benchmark/ab_test_user.py
    python src/benchmark/ab_test_user.py --model-a stepfun/step-3.5-flash:free --model-b nvidia/nemotron-nano-9b-v2:free

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
import subprocess

from openai import OpenAI

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
INPUT_CSV = os.path.join(BASE_DIR, "data", "benchmark", "tickets_scenario_1.csv")
OUTPUT_JSON = os.path.join(BASE_DIR, "data", "benchmark", "ab_user_resultat.json")

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL_A = "stepfun/step-3.5-flash:free"
DEFAULT_MODEL_B = "nvidia/nemotron-nano-9b-v2:free"


def charger_openrouter_api_key() -> str:
    # 1) Standard environment variable for current process/session.
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if key:
        return key

    # 2) Windows fallback: read user-level variable saved by setx.
    if os.name == "nt":
        try:
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "[Environment]::GetEnvironmentVariable('OPENROUTER_API_KEY','User')",
                ],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            fallback = (result.stdout or "").strip()
            if fallback:
                return fallback
        except Exception:
            pass

    return ""


def _extraire_texte(message) -> str:
    content = getattr(message, "content", None)
    if isinstance(content, str) and content.strip():
        return content.strip()

    reasoning = getattr(message, "reasoning", None)
    if isinstance(reasoning, str) and reasoning.strip():
        return reasoning.strip()

    return "[Reponse vide]"


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
    parser = argparse.ArgumentParser(description="Test A/B humain entre deux modeles OpenRouter")
    parser.add_argument("--model-a", default=DEFAULT_MODEL_A, help="Premier modele")
    parser.add_argument("--model-b", default=DEFAULT_MODEL_B, help="Deuxieme modele")
    parser.add_argument("--seed", type=int, default=42, help="Graine aléatoire pour l'ordre A/B")
    parser.add_argument("--retries", type=int, default=3, help="Nombre de tentatives API par appel")
    args = parser.parse_args()

    api_key = charger_openrouter_api_key()
    if not api_key:
        print("Erreur: OPENROUTER_API_KEY introuvable dans l'environnement.")
        print("PowerShell: $env:OPENROUTER_API_KEY = [Environment]::GetEnvironmentVariable('OPENROUTER_API_KEY', 'User')")
        raise SystemExit(1)

    client = OpenAI(api_key=api_key, base_url=OPENROUTER_BASE_URL, timeout=40)

    rng = random.Random(args.seed)

    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        tickets = list(csv.DictReader(f))

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

        while True:
            choix = input("Quelle réponse est meilleure ? (A/B) : ").strip().upper()
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
