"""Run BibOps MCP server."""

from src.bibops.it_support.serveur_mcp import mcp


if __name__ == "__main__":
    mcp.run(transport="stdio")
