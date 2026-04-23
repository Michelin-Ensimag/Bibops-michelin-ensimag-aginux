# Reorganization Map

This map documents where each legacy module is represented in the new structure.

## IT support

- `src/bibops/it_support/maestro.py` -> `src/bibops/it_support/agent.py`
- `src/bibops/it_support/outils.py` -> `src/bibops/it_support/tools.py`
- `src/bibops/it_support/memoire_courte.py` -> `src/bibops/it_support/memory.py`
- `src/bibops/it_support/memoire_RAG.py` -> `src/bibops/it_support/rag.py`
- `src/bibops/it_support/baseSQL.py` -> `src/bibops/it_support/database.py`
- `src/bibops/it_support/serveur_mcp.py` -> `src/bibops/it_support/mcp_server.py`

## Racing

- `src/bibops/racing/*` -> `src/bibops/racing/*`
- `src/bibops/racing/hub/*` -> `src/bibops/racing/hub/*`
- `src/bibops/racing/team_client/*` -> `src/bibops/racing/team_client/*`

## Evaluation

- `src/bibops/evaluation/evaluation.py` -> `src/bibops/evaluation/llm_judge.py`, `src/bibops/evaluation/rule_engine.py`
- `src/bibops/evaluation/discriminator.py` -> `src/bibops/evaluation/discriminator.py`
- `src/bibops/evaluation/adversarial_loop.py` -> `src/bibops/evaluation/adversarial.py`
- `src/bibops/evaluation/rca_engine.py` -> `src/bibops/evaluation/rca.py`
- `src/bibops/evaluation/agent_copilot_mcp.py` -> `src/bibops/evaluation/copilot_mcp.py`

## Benchmark

- `src/bibops/benchmark/benchmark.py` -> `src/bibops/benchmark/core.py`
- `src/bibops/benchmark/benchmark_pipeline.py` -> `src/bibops/benchmark/pipeline.py`
- `src/bibops/benchmark/benchmark_mcp_tools.py` -> `src/bibops/benchmark/mcp_tools.py`

## Operational scripts

- Legacy module entry points are mirrored by wrapper scripts in `scripts/`.
