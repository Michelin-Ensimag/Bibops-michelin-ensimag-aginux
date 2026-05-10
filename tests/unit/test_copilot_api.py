"""
Test de la Copilot API avec plusieurs LLMs sur des tickets IT.

Ce script envoie le même ticket à plusieurs modèles et compare :
- La qualité de la réponse
- Le temps de réponse
- Le nombre de tokens consommés

Prérequis : la Copilot API doit tourner sur localhost:4141
  → npx copilot-api@latest start
"""

import json
import time

import requests

# Ce module est un script de benchmark manuel et ne doit pas être collecté par pytest.
__test__ = False

# === CONFIGURATION ===

# L'adresse de la Copilot API (lancée avec npx copilot-api@latest start)
API_URL = "http://localhost:4141/v1/chat/completions"

# Les modèles à comparer
MODELES = [
    "gpt-4o-mini",
    "gpt-4o",
    "claude-haiku-4.5",
]

# Le ticket IT à tester
TICKET = "Impossible de me connecter au VPN Cisco ce matin, j'ai un message d'erreur 'connection timeout'."

# Le prompt système (le même que dans maestro.py)
SYSTEM_PROMPT = """Tu es l'agent IA de support informatique (BibOps) chez Michelin.
Règles :
1. Sois concis et professionnel
2. Donne des étapes de résolution claires et numérotées
3. Si tu ne peux pas résoudre, recommande l'escalade vers le support niveau 2
"""


# === FONCTION PRINCIPALE ===

def tester_modele(modele, ticket):
    """
    Envoie un ticket à un modèle via la Copilot API et mesure la performance.

    Args:
        modele: Le nom du modèle (ex: "gpt-4o-mini")
        ticket: Le texte du ticket IT

    Returns:
        Dict avec la réponse, le temps et les tokens
    """
    # Construire la requête (format OpenAI)
    payload = {
        "model": modele,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": ticket},
        ],
    }

    # Envoyer la requête et mesurer le temps
    debut = time.time()

    try:
        response = requests.post(API_URL, json=payload, timeout=60)
        temps = time.time() - debut

        data = response.json()

        # Extraire la réponse du LLM
        contenu = data["choices"][0]["message"]["content"]

        # Extraire les tokens
        tokens = data.get("usage", {})
        total_tokens = tokens.get("total_tokens", 0)

        return {
            "modele": modele,
            "reponse": contenu,
            "temps_s": round(temps, 2),
            "total_tokens": total_tokens,
            "statut": "OK",
        }

    except Exception as e:
        temps = time.time() - debut
        return {
            "modele": modele,
            "reponse": str(e),
            "temps_s": round(temps, 2),
            "total_tokens": 0,
            "statut": "ERREUR",
        }


# === EXÉCUTION ===

if __name__ == "__main__":
    print("=" * 60)
    print("BENCHMARK COPILOT API — Tickets IT")
    print("=" * 60)
    print(f"\nTicket : {TICKET}\n")

    resultats = []

    for modele in MODELES:
        print(f"\n--- {modele} ---")
        resultat = tester_modele(modele, TICKET)
        resultats.append(resultat)

        print(f"Statut : {resultat['statut']}")
        print(f"Temps  : {resultat['temps_s']}s")
        print(f"Tokens : {resultat['total_tokens']}")
        print(f"Réponse :\n{resultat['reponse'][:300]}...")

    # Résumé
    print("\n" + "=" * 60)
    print("RÉSUMÉ COMPARATIF")
    print("=" * 60)

    for r in resultats:
        print(f"\n{r['modele']}")
        print(f"  Statut: {r['statut']} | Temps: {r['temps_s']}s | Tokens: {r['total_tokens']}")

    # Sauvegarder les résultats
    with open("data/outputs/benchmark/benchmark_copilot.json", "w", encoding="utf-8") as f:
        json.dump(resultats, f, indent=2, ensure_ascii=False)

    print("\nRésultats sauvegardés dans data/outputs/benchmark/benchmark_copilot.json")
