"""
Agent Copilot + MCP

Ce fichier fait le pont entre :
- Un proxy Copilot/OpenAI-compatible (via variable d'environnement)
- Le serveur MCP (serveur_mcp.py) → accès aux outils (KB, statut serveur, documentation)

Le flux :
1. Se connecter au serveur MCP et récupérer les outils
2. Traduire les outils MCP en format OpenAI (function calling)
3. Envoyer un ticket IT + les outils au LLM via Copilot API
4. Si le LLM veut un outil → l'exécuter via MCP
5. Renvoyer le résultat au LLM → il formule sa réponse finale
6. Scorer la réponse avec le moteur d'évaluation

Prérequis :
- Terminal 1 : démarrer votre proxy OpenAI-compatible
- Terminal 2 : python3 -m src.bibops.llm_professor.agent_copilot_mcp
"""

import asyncio
import json
import time
import sys
import os
import requests
from pathlib import Path

# Import du client MCP
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Import du moteur d'évaluation
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../bibops", "..")))
from .llm_judge import EvaluationEngine


# ============================================================
# CONFIGURATION
# ============================================================

# Configuration via variables d'environnement
COPILOT_API_URL = os.getenv("COPILOT_API_URL")
COPILOT_API_KEY = os.getenv("COPILOT_API_KEY")

# Racine du projet
BASE_DIR = Path(__file__).parent.parent.parent.parent

# Les modèles à comparer
MODELES = [
    "gpt-4o-mini",
    "gpt-4o",
    "claude-haiku-4.5",
]

# Le prompt système de l'agent
SYSTEM_PROMPT = """Tu es l'agent IA de support informatique (BibOps) chez Michelin.

Règles :
1. Utilise TOUJOURS un outil pour chercher une solution avant de répondre.
2. Sois concis et professionnel.
3. Donne des étapes de résolution claires et numérotées.
4. Ne propose JAMAIS d'actions dangereuses sans validation humaine.
"""

# Les tickets de test
TICKETS_TEST = [
    "Mon VPN Cisco ne marche plus, j'ai un message 'connection timeout'.",
    "Outlook crash au démarrage depuis ce matin.",
    "Mon PC est très lent, il met 10 minutes à démarrer.",
    "J'ai oublié mon mot de passe Windows.",
    "Impossible d'accéder au dossier partagé Ressources Humaines.",
]


def _copilot_headers() -> dict:
    headers = {"Content-Type": "application/json"}
    if COPILOT_API_KEY:
        headers["Authorization"] = f"Bearer {COPILOT_API_KEY}"
    return headers


# ============================================================
# ÉTAPE 4 : Traduire les outils MCP → format OpenAI
# ============================================================

def traduire_outils_mcp_vers_openai(outils_mcp):
    """
    Traduit les outils MCP en format OpenAI function calling.

    MCP donne :
        name, description, inputSchema

    OpenAI veut :
        {"type": "function", "function": {"name", "description", "parameters"}}

    C'est le même contenu, juste emballé différemment.
    """
    outils_openai = []

    for outil in outils_mcp:
        outil_openai = {
            "type": "function",
            "function": {
                "name": outil.name,
                "description": outil.description or "",
                "parameters": outil.inputSchema if hasattr(outil, 'inputSchema') else {},
            }
        }
        outils_openai.append(outil_openai)

    return outils_openai


# ============================================================
# ÉTAPES 5-8 : Envoyer au LLM, exécuter l'outil, réponse finale
# ============================================================

async def traiter_ticket(session, ticket, outils_openai, modele):
    """
    Traite un ticket IT complet :
    1. Envoie le ticket + outils au LLM (Copilot API)
    2. Si le LLM veut un outil → l'exécute via MCP
    3. Renvoie le résultat au LLM → réponse finale

    Args:
        session: Session MCP active
        ticket: Le texte du ticket IT
        outils_openai: Les outils traduits en format OpenAI
        modele: Le nom du modèle (ex: "gpt-4o")

    Returns:
        Dict avec la réponse, le temps, les tokens et le statut
    """
    debut = time.time()
    if not COPILOT_API_URL:
        return {
            "modele": modele,
            "ticket": ticket,
            "reponse": "Variable d'environnement manquante: COPILOT_API_URL",
            "outil_utilise": "aucun",
            "temps_s": round(time.time() - debut, 2),
            "tokens": 0,
            "statut": "ERREUR",
        }

    # --- ÉTAPE 5 : Envoyer le ticket + les outils au LLM ---
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": ticket},
    ]

    try:
        response = requests.post(
            COPILOT_API_URL,
            headers=_copilot_headers(),
            json={
                "model": modele,
                "messages": messages,
                "tools": outils_openai,
            },
            timeout=60,
        )

        data = response.json()

        # Vérifier si la réponse est valide
        if "choices" not in data:
            return {
                "modele": modele,
                "ticket": ticket,
                "reponse": f"Erreur API : {data}",
                "outil_utilise": "aucun",
                "temps_s": round(time.time() - debut, 2),
                "tokens": 0,
                "statut": "ERREUR",
            }

        message_llm = data["choices"][0]["message"]

    except Exception as e:
        return {
            "modele": modele,
            "ticket": ticket,
            "reponse": str(e),
            "outil_utilise": "aucun",
            "temps_s": round(time.time() - debut, 2),
            "tokens": 0,
            "statut": "ERREUR",
        }

    # --- ÉTAPE 6 : Le LLM veut-il un outil ? ---
    if "tool_calls" not in message_llm or not message_llm["tool_calls"]:
        # Pas d'outil → réponse directe
        temps = time.time() - debut
        tokens = data.get("usage", {}).get("total_tokens", 0)

        return {
            "modele": modele,
            "ticket": ticket,
            "reponse": message_llm.get("content", ""),
            "outil_utilise": "aucun",
            "temps_s": round(temps, 2),
            "tokens": tokens,
            "statut": "OK",
        }

    # Le LLM veut un outil → on l'exécute
    tool_call = message_llm["tool_calls"][0]
    nom_outil = tool_call["function"]["name"]
    arguments = json.loads(tool_call["function"]["arguments"])

    print(f"    LLM veut appeler : {nom_outil}({arguments})")

    # --- ÉTAPE 7 : Exécuter l'outil via MCP ---
    try:
        resultat_mcp = await session.call_tool(nom_outil, arguments)

        # Extraire le texte du résultat MCP
        resultat_texte = ""
        for block in resultat_mcp.content:
            if hasattr(block, 'text'):
                resultat_texte += block.text

    except Exception as e:
        resultat_texte = f"Erreur lors de l'exécution de l'outil : {e}"

    print(f"    Résultat MCP : {resultat_texte[:100]}...")

    # --- ÉTAPE 8 : Renvoyer le résultat au LLM pour la réponse finale ---
    messages.append(message_llm)  # l'appel d'outil du LLM
    messages.append({
        "role": "tool",
        "content": resultat_texte,
        "tool_call_id": tool_call["id"],
    })

    try:
        response_finale = requests.post(
            COPILOT_API_URL,
            headers=_copilot_headers(),
            json={
                "model": modele,
                "messages": messages,
            },
            timeout=60,
        )

        data_finale = response_finale.json()
        reponse_texte = data_finale["choices"][0]["message"]["content"]

        temps = time.time() - debut
        tokens_1 = data.get("usage", {}).get("total_tokens", 0)
        tokens_2 = data_finale.get("usage", {}).get("total_tokens", 0)

        return {
            "modele": modele,
            "ticket": ticket,
            "reponse": reponse_texte,
            "outil_utilise": nom_outil,
            "temps_s": round(temps, 2),
            "tokens": tokens_1 + tokens_2,
            "statut": "OK",
        }

    except Exception as e:
        return {
            "modele": modele,
            "ticket": ticket,
            "reponse": str(e),
            "outil_utilise": nom_outil,
            "temps_s": round(time.time() - debut, 2),
            "tokens": 0,
            "statut": "ERREUR",
        }


# ============================================================
# FONCTION PRINCIPALE : Benchmark complet
# ============================================================

async def benchmark():
    """
    Lance le benchmark complet :
    - Se connecte au serveur MCP
    - Récupère et traduit les outils
    - Teste chaque ticket avec chaque modèle
    - Score les résultats
    - Sauvegarde dans un JSON
    """

    # Paramètres pour lancer le serveur MCP
    server_params = StdioServerParameters(
        command="python3",
        args=["-m", "src.it_support.mcp_server"],
        cwd=str(BASE_DIR),
    )

    engine = EvaluationEngine()
    tous_les_resultats = []

    # --- ÉTAPE 3 : Se connecter au serveur MCP ---
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            # Récupérer les outils MCP
            response_outils = await session.list_tools()
            print(f"\n{len(response_outils.tools)} outil(s) MCP trouvé(s) :")
            for outil in response_outils.tools:
                print(f"  - {outil.name}")

            # --- ÉTAPE 4 : Traduire en format OpenAI ---
            outils_openai = traduire_outils_mcp_vers_openai(response_outils.tools)
            print(f"\nOutils traduits en format OpenAI : {len(outils_openai)}")

            # --- ÉTAPES 5-9 : Tester chaque ticket avec chaque modèle ---
            for modele in MODELES:
                print(f"\n{'=' * 60}")
                print(f"MODÈLE : {modele}")
                print(f"{'=' * 60}")

                for ticket in TICKETS_TEST:
                    print(f"\n  Ticket : {ticket[:60]}...")

                    # Traiter le ticket (étapes 5 à 8)
                    resultat = await traiter_ticket(
                        session, ticket, outils_openai, modele
                    )

                    # --- ÉTAPE 9 : Scorer avec le moteur de Widad ---
                    reponse_eval = resultat["reponse"] if resultat["statut"] == "OK" else "ERREUR"
                    feedback = "Utile" if resultat["statut"] == "OK" else "Inutile"

                    scores = engine.calculate_final_score(
                        reponse=reponse_eval,
                        feedback=feedback,
                        temps_secondes=resultat["temps_s"],
                        nombre_tokens=resultat["tokens"],
                    )

                    resultat["scores"] = scores
                    tous_les_resultats.append(resultat)

                    print(f"    Statut : {resultat['statut']}")
                    print(f"    Outil  : {resultat['outil_utilise']}")
                    print(f"    Temps  : {resultat['temps_s']}s")
                    print(f"    Score  : {scores['score_final']}/10")
                    print(f"    Réponse : {resultat['reponse'][:150]}...")

    return tous_les_resultats


# ============================================================
# POINT D'ENTRÉE
# ============================================================

async def main():
    print("=" * 60)
    print("AGENT COPILOT + MCP — Benchmark multi-modèles")
    print("=" * 60)

    # Lancer le benchmark
    resultats = await benchmark()

    # Résumé comparatif
    print("\n" + "=" * 60)
    print("RÉSUMÉ COMPARATIF")
    print("=" * 60)

    for modele in MODELES:
        resultats_modele = [r for r in resultats if r["modele"] == modele]
        scores = [r["scores"]["score_final"] for r in resultats_modele]
        temps = [r["temps_s"] for r in resultats_modele]
        outils_utilises = sum(1 for r in resultats_modele if r["outil_utilise"] != "aucun")

        if scores:
            print(f"\n{modele}")
            print(f"  Score moyen  : {sum(scores) / len(scores):.2f}/10")
            print(f"  Temps moyen  : {sum(temps) / len(temps):.2f}s")
            print(f"  Outils utilisés : {outils_utilises}/{len(resultats_modele)}")

    # --- ÉTAPE 11 : Sauvegarder ---
    output_dir = BASE_DIR / "data" / "outputs" / "benchmark"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "benchmark_copilot_mcp.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(resultats, f, indent=2, ensure_ascii=False)

    print(f"\nRésultats sauvegardés dans : {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
