"""Run BibOps MCP server."""

from src.it_support.mcp_server import mcp


if __name__ == "__main__":
    mcp.run(transport="stdio")
