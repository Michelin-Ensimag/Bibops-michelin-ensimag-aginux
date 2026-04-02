"""
Test A/B automatique : compare deux modeles OpenRouter avec un LLM juge.

Usage (PowerShell):
    $env:OPENROUTER_API_KEY = [Environment]::GetEnvironmentVariable("OPENROUTER_API_KEY", "User")
    python src/benchmark/ab_test_llm.py

Le script lit les tickets depuis tickets_scenario_1.csv, genere une reponse
par modele, puis demande a un modele juge de choisir la meilleure reponse.
Le jugement se fait en une seule passe pour privilegier la rapidite.
"""

import argparse
import csv
import json
import os
import random
import subprocess
from typing import Any, Dict, Optional, Tuple

from openai import OpenAI

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
INPUT_CSV = os.path.join(BASE_DIR, "data", "benchmark", "tickets_scenario_1.csv")
OUTPUT_JSON = os.path.join(BASE_DIR, "data", "benchmark", "ab_llm_resultat.json")

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL_A = "stepfun/step-3.5-flash:free"
DEFAULT_MODEL_B = "nvidia/nemotron-nano-9b-v2:free"
DEFAULT_JUDGE_MODEL = "qwen/qwen3-32b:free"
RANDOM_SEED = 42

JUDGE_SYSTEM_PROMPT = (
    "Tu es un evaluateur impartial de reponses de support IT. "
    "Tu dois choisir la meilleure reponse entre A et B selon des criteres precis : "
    "pertinence, clarte, actionabilite, et adaptation au contexte. "
    "Retourne uniquement un JSON valide sans texte additionnel."
)


def charger_openrouter_api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if key:
        return key

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


def _extraire_texte(message: Any) -> str:
    content = getattr(message, "content", None)
    if isinstance(content, str) and content.strip():
        return content.strip()

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
        if parts:
            return "\n".join(parts)

    reasoning = getattr(message, "reasoning", None)
    if isinstance(reasoning, str) and reasoning.strip():
        return reasoning.strip()

    return "[Reponse vide]"


def appeler_modele(client: OpenAI, modele: str, contexte: str, ticket: str) -> str:
    try:
        reponse = client.chat.completions.create(
            model=modele,
            messages=[
                {"role": "system", "content": contexte},
                {"role": "user", "content": ticket},
            ],
            max_tokens=384,
            temperature=0,
        )
        return _extraire_texte(reponse.choices[0].message)
    except Exception as exc:
        return f"[ERREUR_MODELE {modele}] {exc}"


def _construire_prompt_juge(contexte: str, question: str, reponse_a: str, reponse_b: str) -> str:
    return (
        "Contexte metier:\n"
        f"{contexte}\n\n"
        "Question utilisateur:\n"
        f"{question}\n\n"
        "Reponse A:\n"
        f"{reponse_a}\n\n"
        "Reponse B:\n"
        f"{reponse_b}\n\n"
        "Choisis la meilleure reponse (A ou B). "
        "Tu dois favoriser la reponse la plus pertinente, claire, actionnable et adaptee au contexte utilisateur.\n"
        "Retour attendu (JSON strict):\n"
        "{\n"
        '  "choix": "A" ou "B",\n'
        '  "justification": "1-2 phrases"\n'
        "}"
    )


def _extraire_json_depuis_texte(texte: str) -> Optional[Dict[str, Any]]:
    brut = texte.strip()
    try:
        obj = json.loads(brut)
        if isinstance(obj, dict):
            return obj
    except Exception:
        return None


def _normaliser_choix(choix: Any) -> Optional[str]:
    if not isinstance(choix, str):
        return None
    c = choix.strip().upper()
    if c in ("A", "B"):
        return c
    return None


def appeler_juge(
    client: OpenAI,
    modele_juge: str,
    prompt_juge: str,
) -> Tuple[Optional[Dict[str, Any]], str]:
    try:
        reponse = client.chat.completions.create(
            model=modele_juge,
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt_juge},
            ],
            max_tokens=180,
            temperature=0,
        )
        texte = _extraire_texte(reponse.choices[0].message)
        obj = _extraire_json_depuis_texte(texte)
        if obj is None:
            return None, f"JSON invalide: {texte[:200]}"

        choix = _normaliser_choix(obj.get("choix"))
        if choix is None:
            return None, f"Champ choix invalide: {obj}"

        justification = obj.get("justification", "")
        return (
            {
                "choix": choix,
                "justification": str(justification),
            },
            "",
        )
    except Exception as exc:
        return None, str(exc)


def evaluer_ticket_avec_juge_robuste(
    client: OpenAI,
    modele_juge: str,
    contexte: str,
    question: str,
    reponse_a: str,
    reponse_b: str,
) -> Dict[str, Any]:
    prompt = _construire_prompt_juge(contexte, question, reponse_a, reponse_b)
    res, err = appeler_juge(client, modele_juge, prompt)
    if res is None:
        return {
            "ok": False,
            "erreur": err,
            "choix": "",
            "justification": "",
        }

    return {
        "ok": True,
        "erreur": "",
        "choix": res["choix"],
        "justification": res["justification"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test A/B automatique (LLM juge) entre deux modeles OpenRouter"
    )
    parser.add_argument("--model-a", default=DEFAULT_MODEL_A, help="Premier modele")
    parser.add_argument("--model-b", default=DEFAULT_MODEL_B, help="Deuxieme modele")
    parser.add_argument(
        "--judge-model",
        default=DEFAULT_JUDGE_MODEL,
        help="Modele juge principal (OpenRouter)",
    )
    parser.add_argument(
        "--output",
        default=OUTPUT_JSON,
        help="Chemin du JSON de resultats",
    )
    args = parser.parse_args()

    api_key = charger_openrouter_api_key()
    if not api_key:
        print("Erreur: OPENROUTER_API_KEY introuvable dans l'environnement.")
        print(
            "PowerShell: $env:OPENROUTER_API_KEY = "
            "[Environment]::GetEnvironmentVariable('OPENROUTER_API_KEY', 'User')"
        )
        raise SystemExit(1)

    client = OpenAI(api_key=api_key, base_url=OPENROUTER_BASE_URL, timeout=35)
    rng = random.Random(RANDOM_SEED)

    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        tickets = list(csv.DictReader(f))

    resultats = []
    scores = {args.model_a: 0, args.model_b: 0}

    print(
        f"\n=== Evaluation A/B LLM Judge : {args.model_a} vs {args.model_b} ==="
    )
    print(f"Juge principal : {args.judge_model}")
    print(f"{len(tickets)} ticket(s) a evaluer.\n")

    for ticket in tickets:
        tid = ticket["id"]
        contexte = ticket["contexte"]
        question = ticket["ticket"]

        print(f"--- Ticket #{tid} ---")
        print(f"Question : {question}\n")
        print("Generation des reponses en cours...")

        rep_modele_a = appeler_modele(client, args.model_a, contexte, question)
        rep_modele_b = appeler_modele(client, args.model_b, contexte, question)

        # Blindage: ordre aleatoire avant passage au juge.
        if rng.random() < 0.5:
            label_a, rep_a = args.model_a, rep_modele_a
            label_b, rep_b = args.model_b, rep_modele_b
        else:
            label_a, rep_a = args.model_b, rep_modele_b
            label_b, rep_b = args.model_a, rep_modele_a

        print("Evaluation par le juge LLM...")
        jugement = evaluer_ticket_avec_juge_robuste(
            client=client,
            modele_juge=args.judge_model,
            contexte=contexte,
            question=question,
            reponse_a=rep_a,
            reponse_b=rep_b,
        )

        if not jugement.get("ok"):
            err = jugement.get("erreur", "Erreur inconnue")
            print(f"[ERREUR_JUGE] {err}")
            meilleur_modele = "[INDETERMINE]"
            choix_llm = "?"
            justification_juge = ""
        else:
            choix_llm = jugement["choix"]
            meilleur_modele = label_a if choix_llm == "A" else label_b
            justification_juge = jugement["justification"]
            scores[meilleur_modele] += 1
            print(f"-> Choix juge: {choix_llm} | Meilleur modele: {meilleur_modele}")

        resultats.append(
            {
                "ticket_id": tid,
                "question": question,
                "choix_llm": choix_llm,
                "meilleur_modele": meilleur_modele,
                "justification_juge": justification_juge,
            }
        )

        print()

    print("=== Synthese des votes ===")
    total_votes = sum(scores.values())
    pourcentages: Dict[str, float] = {}

    for modele, score in scores.items():
        pct = round((score / total_votes) * 100, 1) if total_votes else 0.0
        pourcentages[modele] = pct
        print(f"  {modele} : {score} vote(s) ({pct:.1f}%)")

    payload = {
        "modeles": [args.model_a, args.model_b],
        "juge": args.judge_model,
        "scores": scores,
        "pourcentages": pourcentages,
        "details": resultats,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"\nResultats sauvegardes dans {args.output}")


if __name__ == "__main__":
    main()
