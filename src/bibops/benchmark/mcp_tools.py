"""
Benchmark des outils MCP via le protocole MCP sur stdio.

Ce client se connecte au serveur MCP (serveur_mcp.py) pour :
1. Découvrir les outils disponibles de l'agent BibOps
2. Appeler ces outils avec des tickets de test
3. Mesurer les temps de réponse
4. Évaluer les résultats avec EvaluationEngine (scoring par règles)

Communication : stdin/stdout (protocole MCP sur stdio)
"""

import asyncio
import json
import time

# Import du client MCP
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from src.bibops.evaluation.judges.rule_engine import EvaluationEngine
from src.common.config import BASE_DIR

# === CONFIGURATION ===

# Tickets de test (même format que tickets_evalues_fake.json)
TICKETS_TEST = [
    {
        "id_ticket": "MCP-001",
        "ticket": "Mon VPN Cisco ne marche plus.",
        "outil_attendu": "mcp_chercher_dans_kb",
        "argument": {"requete": "vpn ne marche pas"},
    },
    {
        "id_ticket": "MCP-002",
        "ticket": "Est-ce que le service Mail est en ligne ?",
        "outil_attendu": "mcp_verifier_statut_serveur",
        "argument": {"nom_serveur": "MAIL"},
    },
    {
        "id_ticket": "MCP-003",
        "ticket": "Comment récupérer ma clé Bitlocker ?",
        "outil_attendu": "mcp_chercher_documentation_technique",
        "argument": {"mot_cle": "bitlocker"},
    },
    {
        "id_ticket": "MCP-004",
        "ticket": "Mon PC est très lent depuis ce matin.",
        "outil_attendu": "mcp_chercher_dans_kb",
        "argument": {"requete": "pc lent"},
    },
    {
        "id_ticket": "MCP-005",
        "ticket": "Outlook crash au démarrage.",
        "outil_attendu": "mcp_chercher_dans_kb",
        "argument": {"requete": "outlook crash"},
    },
]


# === FONCTIONS PRINCIPALES ===

async def connecter_et_lister_outils():
    """
    Se connecte au serveur MCP et retourne la liste des outils disponibles.

    Returns:
        Liste des outils avec leur nom, description et paramètres.
    """
    server_params = StdioServerParameters(
        command="python3",
        args=["-m", "src.agent.mcp_server"],
        cwd=str(BASE_DIR),
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            # Handshake avec le serveur
            await session.initialize()

            # Demander la liste des outils
            response = await session.list_tools()

            outils = []
            for tool in response.tools:
                outils.append({
                    "nom": tool.name,
                    "description": tool.description,
                    "parametres": tool.inputSchema if hasattr(tool, 'inputSchema') else {},
                })

            return outils


async def appeler_outil(session, nom_outil: str, arguments: dict) -> dict:
    """
    Appelle un outil sur le serveur MCP et mesure le temps de réponse.

    Args:
        session: Session MCP active.
        nom_outil: Nom de l'outil à appeler.
        arguments: Dict des arguments à passer à l'outil.

    Returns:
        Dict avec le résultat, le temps de réponse et le statut.
    """
    debut = time.time()

    try:
        resultat = await session.call_tool(nom_outil, arguments)
        temps = time.time() - debut

        # Extraire le texte du résultat MCP
        contenu = ""
        for block in resultat.content:
            if hasattr(block, 'text'):
                contenu += block.text

        return {
            "statut": "OK",
            "resultat": contenu,
            "temps_reponse_s": round(temps, 3),
        }

    except Exception as e:
        temps = time.time() - debut
        return {
            "statut": "ERREUR",
            "resultat": str(e),
            "temps_reponse_s": round(temps, 3),
        }


async def benchmark_outils():
    """
    Teste chaque outil MCP avec les tickets de test.
    Mesure les temps de réponse et évalue les résultats.

    Returns:
        Dict avec les résultats du benchmark.
    """
    server_params = StdioServerParameters(
        command="python3",
        args=["-m", "src.agent.mcp_server"],
        cwd=str(BASE_DIR),
    )

    resultats_benchmark = []
    engine = EvaluationEngine()

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            # Pour chaque ticket de test
            for ticket in TICKETS_TEST:
                print(f"\n--- Test {ticket['id_ticket']} ---")
                print(f"Ticket : {ticket['ticket']}")
                print(f"Outil  : {ticket['outil_attendu']}")

                # Appeler l'outil
                resultat = await appeler_outil(
                    session,
                    ticket["outil_attendu"],
                    ticket["argument"],
                )

                print(f"Statut : {resultat['statut']}")
                print(f"Temps  : {resultat['temps_reponse_s']}s")
                print(f"Résultat (extrait) : {resultat['resultat'][:150]}...")

                # Évaluer avec le moteur existant
                reponse_pour_eval = resultat["resultat"] if resultat["statut"] == "OK" else "ERREUR"
                # Feedback simulé : "Utile" si résultat OK, "Inutile" si erreur
                feedback = "Utile" if resultat["statut"] == "OK" else "Inutile"

                scores = engine.calculate_final_score(
                    reponse=reponse_pour_eval,
                    feedback=feedback,
                    temps_secondes=resultat["temps_reponse_s"],
                    nombre_tokens=len(resultat["resultat"].split()),  # approximation
                )

                resultats_benchmark.append({
                    "id_ticket": ticket["id_ticket"],
                    "ticket": ticket["ticket"],
                    "outil": ticket["outil_attendu"],
                    "statut": resultat["statut"],
                    "temps_reponse_s": resultat["temps_reponse_s"],
                    "scores": scores,
                })

                print(f"Score final : {scores['score_final']}/10")

    return resultats_benchmark


async def sauvegarder_benchmark(resultats: list):
    """
    Sauvegarde les résultats du benchmark dans un fichier JSON.
    """
    output_dir = BASE_DIR / "data" / "outputs" / "benchmark"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / "benchmark_mcp_tools.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(resultats, f, indent=2, ensure_ascii=False)

    print(f"\nRésultats sauvegardés dans : {output_path}")


# === POINT D'ENTRÉE ===

async def main():
    """Point d'entrée principal."""

    print("=" * 60)
    print("BENCHMARK MCP TOOLS")
    print("=" * 60)

    # 1. Lister les outils disponibles
    print("\n[1] Découverte des outils MCP...")
    outils = await connecter_et_lister_outils()

    print(f"\n{len(outils)} outil(s) trouvé(s) :")
    for outil in outils:
        print(f"  - {outil['nom']} : {outil['description']}")

    # 2. Benchmark des outils
    print("\n[2] Benchmark des outils...")
    resultats = await benchmark_outils()

    # 3. Résumé
    print("\n" + "=" * 60)
    print("RÉSUMÉ DU BENCHMARK")
    print("=" * 60)

    for r in resultats:
        print(f"\n{r['id_ticket']} | {r['outil']}")
        print(f"  Statut: {r['statut']} | Temps: {r['temps_reponse_s']}s | Score: {r['scores']['score_final']}/10")

    # 4. Sauvegarde
    await sauvegarder_benchmark(resultats)


if __name__ == "__main__":
    asyncio.run(main())
