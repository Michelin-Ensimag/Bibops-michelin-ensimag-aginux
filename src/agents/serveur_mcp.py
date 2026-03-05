from mcp.server.fastmcp import FastMCP
import sqlite3
import chromadb
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
DB_PATH = os.path.join(BASE_DIR, 'data', 'bibops.db')
CHROMA_PATH = os.path.join(BASE_DIR, 'data', 'vectordb')

mcp = FastMCP("Michelin_IT_Tools")

@mcp.tool()
def verifier_statut_serveur(nom_serveur: str) -> str:
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT statut FROM serveurs_it WHERE nom = ?", (nom_serveur.upper(),))
        resultat = cursor.fetchone()
        conn.close()

        if resultat:
            return f"Statut : Le service {nom_serveur} est {resultat[0]}."
        return f"Service inconnu : Aucun serveur nommé {nom_serveur}."
    except Exception as e:
        return f"Erreur SQL : {e}"

@mcp.tool()
def chercher_documentation_technique(mot_cle: str) -> str:
    try:
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        collection = client.get_collection(name="doc_michelin")

        resultats = collection.query(query_texts=[mot_cle], n_results=1)
        doc_trouve = resultats['documents'][0][0]
        return f"Documentation trouvée : {doc_trouve}"
    except Exception as e:
        return f"Aucune documentation trouvée. Erreur: {e}"

if __name__ == "__main__":
    print("Démarrage du Serveur MCP Michelin...")
    mcp.run_stdio_async()