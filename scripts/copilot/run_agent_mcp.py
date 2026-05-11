"""Run Copilot + MCP multi-model benchmark."""

import asyncio

from src.bibops.research.mcp_demos.copilot_mcp import main


if __name__ == "__main__":
    asyncio.run(main())
