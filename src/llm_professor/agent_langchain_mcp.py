"""
Agent Copilot + MCP — Version LangGraph

Ce fichier fait la même chose que agent_copilot_mcp.py mais avec LangGraph
au lieu de requêtes HTTP brutes.

Avantages :
- Boucle multi-outils automatique
- Gestion d'erreurs automatique
- Code plus court et plus lisible

Prérequis :
- Terminal : python3 -m src.llm_professor.agent_langchain_mcp
"""

import asyncio
import json
import time
import sys
import os
from pathlib import Path

# LangChain : pour parler à la Copilot API
from langchain_openai import ChatOpenAI

# LangChain : pour transformer les outils MCP en outils LangChain
from langchain_core.tools import StructuredTool

# LangGraph : crée un agent ReAct automatique
from langgraph.prebuilt import create_react_agent

# MCP : pour se connecter au serveur MCP
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Moteur d'évaluation (celui de Widad)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

try:
    from src.llm_professor.evaluation import EvaluationEngine
except ImportError:
    from evaluation import EvaluationEngine


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).parent.parent.parent

MODELES = [
    "gpt-4o-mini",
    "gpt-4o",
    "claude-haiku-4.5",
]

# MODELES = [
#     "google/gemini-3-flash-preview",
#     "anthropic/claude-sonnet-4.5",
#     "qwen/qwen3.6-plus:free"
# ]

SYSTEM_PROMPT = """Tu es l'agent IA de support informatique (BibOps) chez Michelin.

Règles :
1. Utilise TOUJOURS un outil pour chercher une solution avant de répondre.
2. Sois concis et professionnel.
3. Donne des étapes de résolution claires et numérotées.
4. Ne propose JAMAIS d'actions dangereuses sans validation humaine.
5. Si un outil échoue, essaie un autre outil disponible.
"""

# SYSTEM_PROMPT = """Tu es l'agent IA de support informatique (BibOps) chez Michelin.

# RÈGLE ABSOLUE :
# Tu dois utiliser un outil pour répondre.

# FORMAT OBLIGATOIRE :

# Thought: ...
# Action: nom_de_l_outil
# Action Input: ...

# Tu n'as PAS le droit de répondre directement.

# Après avoir utilisé un outil, tu dois répondre avec les informations retournées.
# """

TICKETS_TEST = [
    "Mon VPN Cisco ne marche plus, j'ai un message 'connection timeout'.",
    "Outlook crash au démarrage depuis ce matin.",
    "Mon PC est très lent, il met 10 minutes à démarrer.",
    "J'ai oublié mon mot de passe Windows.",
    "Impossible d'accéder au dossier partagé Ressources Humaines.",
]


# ============================================================
# ÉTAPE 1 : Convertir les outils MCP en outils LangChain
# ============================================================

def creer_outil_langchain(session, outil_mcp):
    nom = outil_mcp.name
    description = outil_mcp.description or ""

    async def appeler_outil_async(**kwargs):
        resultat = await session.call_tool(nom, kwargs)
        contenu = ""
        for block in resultat.content:
            if hasattr(block, "text"):
                contenu += block.text
        return contenu

    return StructuredTool.from_function(
        func=appeler_outil_async, 
        name=nom,
        description=description,
        coroutine=appeler_outil_async 
    )


async def recuperer_outils_langchain(session):
    """Récupère les outils MCP et les convertit en outils LangChain."""
    response = await session.list_tools()
    outils = []
    for outil in response.tools:
        outil_lc = creer_outil_langchain(session, outil)
        outils.append(outil_lc)
        print(f"  - {outil.name} → converti en outil LangChain")
    return outils


# ============================================================
# ÉTAPE 2 : Créer l'agent LangGraph
# ============================================================

def creer_agent(modele, outils):
    """Crée un agent ReAct avec LangGraph."""
    llm = ChatOpenAI(
        base_url="http://localhost:4141/v1",
        api_key="dummy",
        model=modele,
        temperature=0,
    )
    # llm = ChatOpenAI(
    #     base_url="https://openrouter.ai/api/v1",
    #     api_key="***OPENROUTER_KEY_REMOVED***",
    #     model=modele,
    #     temperature=0,
    # )
    agent = create_react_agent(llm, outils, prompt=SYSTEM_PROMPT)
    return agent


# ============================================================
# ÉTAPE 3 : Traiter un ticket
# ============================================================

async def traiter_ticket(agent, ticket, modele):
    debut = time.time()

    try:
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": ticket}]}
        )

        temps = time.time() - debut
        derniere_reponse = result["messages"][-1].content

        return {
            "modele": modele,
            "ticket": ticket,
            "reponse": derniere_reponse,
            "outil_utilise": "auto (LangGraph)",
            "temps_s": round(temps, 2),
            "tokens": 0,
            "statut": "OK",
        }

    except Exception as e:
        temps = time.time() - debut
        return {
            "modele": modele,
            "ticket": ticket,
            "reponse": str(e),
            "outil_utilise": "aucun",
            "temps_s": round(temps, 2),
            "tokens": 0,
            "statut": "ERREUR",
        }


# ============================================================
# BENCHMARK COMPLET
# ============================================================

async def benchmark():
    server_params = StdioServerParameters(
        command="python3",
        args=["-m", "src.agents.serveur_mcp"],
        cwd=str(BASE_DIR),
    )

    engine = EvaluationEngine()
    tous_les_resultats = []

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            print("\n[1] Conversion des outils MCP → LangChain...")
            outils = await recuperer_outils_langchain(session)
            print(f"\n{len(outils)} outil(s) prêt(s)\n")

            for modele in MODELES:
                print(f"\n{'=' * 60}")
                print(f"MODÈLE : {modele}")
                print(f"{'=' * 60}")

                agent = creer_agent(modele, outils)

                for ticket in TICKETS_TEST:
                    print(f"\n  Ticket : {ticket[:60]}...")
                    resultat = await traiter_ticket(agent, ticket, modele)

                    reponse_eval = resultat["reponse"] if resultat["statut"] == "OK" else "ERREUR"
                    feedback = "Utile" if resultat["statut"] == "OK" else "Inutile"

                    scores = engine.calculate_final_score(
                        reponse=reponse_eval,
                        feedback=feedback,
                        temps_secondes=resultat["temps_s"],
                        nombre_tokens=len(resultat["reponse"].split()),
                    )

                    resultat["scores"] = scores
                    tous_les_resultats.append(resultat)

                    print(f"    Statut : {resultat['statut']}")
                    print(f"    Temps  : {resultat['temps_s']}s")
                    print(f"    Score  : {scores['score_final']}/10")
                    print(f"    Réponse : {resultat['reponse'][:150]}...")

    return tous_les_resultats


# ============================================================
# POINT D'ENTRÉE
# ============================================================

async def main():
    print("=" * 60)
    print("AGENT LANGGRAPH + MCP — Benchmark multi-modèles")
    print("=" * 60)

    resultats = await benchmark()

    print("\n" + "=" * 60)
    print("RÉSUMÉ COMPARATIF")
    print("=" * 60)

    for modele in MODELES:
        resultats_modele = [r for r in resultats if r["modele"] == modele]
        scores = [r["scores"]["score_final"] for r in resultats_modele]
        temps = [r["temps_s"] for r in resultats_modele]

        if scores:
            print(f"\n{modele}")
            print(f"  Score moyen : {sum(scores) / len(scores):.2f}/10")
            print(f"  Temps moyen : {sum(temps) / len(temps):.2f}s")

    output_dir = BASE_DIR / "data" / "benchmark"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "benchmark_langchain_mcp.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(resultats, f, indent=2, ensure_ascii=False)

    print(f"\nRésultats sauvegardés dans : {output_path}")


if __name__ == "__main__":
    asyncio.run(main())