"""Run BibOps MCP server."""

from src.agent.mcp_server import mcp


if __name__ == "__main__":
    mcp.run(transport="stdio")
