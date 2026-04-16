# Reorganization Map

This map documents where each legacy module is represented in the new structure.

## IT support

- `src/agents/maestro.py` -> `src/bibops/it_support/agent.py`
- `src/agents/outils.py` -> `src/bibops/it_support/tools.py`
- `src/agents/memoire_courte.py` -> `src/bibops/it_support/memory.py`
- `src/agents/memoire_RAG.py` -> `src/bibops/it_support/rag.py`
- `src/agents/baseSQL.py` -> `src/bibops/it_support/database.py`
- `src/agents/serveur_mcp.py` -> `src/bibops/it_support/mcp_server.py`

## Racing

- `src/agents_racing/*` -> `src/bibops/racing/*`
- `src/agents_racing/hub/*` -> `src/bibops/racing/hub/*`
- `src/agents_racing/team_client/*` -> `src/bibops/racing/team_client/*`

## Evaluation

- `src/llm_professor/evaluation.py` -> `src/bibops/evaluation/llm_judge.py`, `src/bibops/evaluation/rule_engine.py`
- `src/llm_professor/discriminator.py` -> `src/bibops/evaluation/discriminator.py`
- `src/llm_professor/adversarial_loop.py` -> `src/bibops/evaluation/adversarial.py`
- `src/llm_professor/rca_engine.py` -> `src/bibops/evaluation/rca.py`
- `src/llm_professor/agent_copilot_mcp.py` -> `src/bibops/evaluation/copilot_mcp.py`

## Benchmark

- `src/benchmark/benchmark.py` -> `src/bibops/benchmark/core.py`
- `src/benchmark/benchmark_pipeline.py` -> `src/bibops/benchmark/pipeline.py`
- `src/benchmark/benchmark_mcp_tools.py` -> `src/bibops/benchmark/mcp_tools.py`

## Operational scripts

- Legacy module entry points are mirrored by wrapper scripts in `scripts/`.
