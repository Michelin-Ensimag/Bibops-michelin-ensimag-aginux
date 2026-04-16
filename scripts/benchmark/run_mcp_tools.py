"""Run the MCP tools benchmark (wrapper script)."""

import asyncio

from src.benchmark.benchmark_mcp_tools import main


if __name__ == "__main__":
    asyncio.run(main())
