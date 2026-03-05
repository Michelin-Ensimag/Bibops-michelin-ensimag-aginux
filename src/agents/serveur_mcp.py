import sys
import os

# 1. On force Python à reconnaître la racine du projet pour trouver "src"
# ⚠️ CELA DOIT ÊTRE PLACÉ AVANT L'IMPORT DE 'src.agents...'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# 2. Maintenant on peut faire nos imports
from mcp.server.fastmcp import FastMCP
from src.agents.outils import verifier_statut_serveur
import chromadb

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
DB_PATH = os.path.join(BASE_DIR, 'data', 'bibops.db')
CHROMA_PATH = os.path.join(BASE_DIR, 'data', 'vectordb')

mcp = FastMCP("Michelin_IT_Tools")

# On "branche" l'outil existant sur la multiprise MCP
@mcp.tool()
def mcp_verifier_statut_serveur(nom_serveur: str) -> str:
    return verifier_statut_serveur(nom_serveur)

@mcp.tool()
def chercher_documentation_technique(mot_cle: str) -> str:
    """Cherche dans la documentation technique vectorielle de Michelin une procédure de résolution."""
    try:
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        collection = client.get_collection(name="doc_michelin")

        resultats = collection.query(query_texts=[mot_cle], n_results=1)

        # On récupère le texte ET l'identifiant (le nom du KB)
        doc_trouve = resultats['documents'][0][0]
        kb_id = resultats['ids'][0][0]

        return f"Documentation trouvée (Source: {kb_id}) :\n{doc_trouve}"
    except Exception as e:
        return f"Aucune documentation trouvée. Erreur: {e}"

if __name__ == "__main__":
    print("Démarrage du Serveur MCP Michelin...")
    mcp.run_stdio_async()