"""Run Copilot + MCP multi-model benchmark."""

import asyncio

from src.llm_professor.agent_copilot_mcp import main


if __name__ == "__main__":
    asyncio.run(main())
