"""Run the MCP tools benchmark (wrapper script)."""

import asyncio

from src.bibops.benchmark.mcp_tools import main


if __name__ == "__main__":
    asyncio.run(main())
