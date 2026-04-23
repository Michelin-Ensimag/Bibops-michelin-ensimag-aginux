from mcp.server.fastmcp import FastMCP

from .outils import (
    chercher_dans_kb,
    chercher_documentation_technique,
    verifier_statut_serveur,
)

mcp = FastMCP("Michelin_IT_Tools")

# On "branche" les outils existants sur la multiprise MCP
@mcp.tool()
def mcp_verifier_statut_serveur(nom_serveur: str) -> str:
    """Vérifie l'état d'un serveur dans la base de données SQLite."""
    return verifier_statut_serveur(nom_serveur)

@mcp.tool()
def mcp_chercher_documentation_technique(mot_cle: str) -> str:
    """Cherche dans la documentation technique vectorielle de Michelin une procédure de résolution."""
    return chercher_documentation_technique(mot_cle)

@mcp.tool()
def mcp_chercher_dans_kb(requete: str) -> str:
    """Recherche des solutions dans la Knowledge Base JSON pour un problème IT."""
    return chercher_dans_kb(requete)

# if __name__ == "__main__":
#     print("Démarrage du Serveur MCP Michelin...")
#     mcp.run_stdio_async()



if __name__ == "__main__":
    mcp.run(transport="stdio")
