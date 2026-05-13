"""Copilot OpenAI-compatible API smoke test used by `bibops copilot smoke-test`."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import requests

from src.common.config import BASE_DIR, COPILOT_BASE_URL

DEFAULT_MODELS = ("gpt-4o-mini", "gpt-4o", "claude-haiku-4.5")
DEFAULT_TICKET = "Impossible de me connecter au VPN Cisco ce matin, j'ai un message d'erreur 'connection timeout'."
DEFAULT_OUTPUT = BASE_DIR / "data" / "outputs" / "benchmark" / "benchmark_copilot.json"

SYSTEM_PROMPT = """Tu es l'agent IA de support informatique (BibOps) chez Michelin.
Règles :
1. Sois concis et professionnel
2. Donne des étapes de résolution claires et numérotées
3. Si tu ne peux pas résoudre, recommande l'escalade vers le support niveau 2
"""


def tester_modele(modele: str, ticket: str, api_url: str) -> dict[str, Any]:
    """Send one support ticket to a model through the Copilot proxy."""
    payload = {
        "model": modele,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": ticket},
        ],
    }

    start = time.time()
    try:
        response = requests.post(api_url, json=payload, timeout=60)
        elapsed = time.time() - start
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return {
            "modele": modele,
            "reponse": content,
            "temps_s": round(elapsed, 2),
            "total_tokens": usage.get("total_tokens", 0),
            "statut": "OK",
        }
    except Exception as exc:
        elapsed = time.time() - start
        return {
            "modele": modele,
            "reponse": str(exc),
            "temps_s": round(elapsed, 2),
            "total_tokens": 0,
            "statut": "ERREUR",
        }


def run_smoke_test(models: list[str], ticket: str, api_url: str, output_json: Path) -> list[dict[str, Any]]:
    """Run the smoke test and persist the JSON result."""
    print("=" * 60)
    print("BENCHMARK COPILOT API - Tickets IT")
    print("=" * 60)
    print(f"\nTicket : {ticket}\n")

    results = []
    for model in models:
        print(f"\n--- {model} ---")
        result = tester_modele(model, ticket, api_url)
        results.append(result)
        print(f"Statut : {result['statut']}")
        print(f"Temps  : {result['temps_s']}s")
        print(f"Tokens : {result['total_tokens']}")
        print(f"Réponse :\n{result['reponse'][:300]}...")

    print("\n" + "=" * 60)
    print("RESUME COMPARATIF")
    print("=" * 60)
    for result in results:
        print(
            f"\n{result['modele']}\n"
            f"  Statut: {result['statut']} | Temps: {result['temps_s']}s | Tokens: {result['total_tokens']}"
        )

    output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nRésultats sauvegardés dans {output_json}")
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Copilot API smoke test on one IT support ticket.")
    parser.add_argument("--api-url", default=f"{COPILOT_BASE_URL.rstrip('/')}/chat/completions")
    parser.add_argument("--model", action="append", dest="models", help="Model to test. Repeat to test several models.")
    parser.add_argument("--ticket", default=DEFAULT_TICKET)
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args(argv)

    run_smoke_test(
        models=args.models or list(DEFAULT_MODELS),
        ticket=args.ticket,
        api_url=args.api_url,
        output_json=Path(args.output_json),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
