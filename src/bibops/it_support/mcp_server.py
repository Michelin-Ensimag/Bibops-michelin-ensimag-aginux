"""MCP server wrapper."""

from src.agents.serveur_mcp import mcp

__all__ = ["mcp"]


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
