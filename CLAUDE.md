# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

BibOps is an LLM evaluation framework for Michelin IT support, comparing two architectures:
- **LLM Unique** (zero-shot, no tools)
- **Système Multi-Agents** (ReAct loop + KB search + RAG + server status tools)

It also includes a **Racing Arena**: a distributed multi-agent system where LLM-powered F1 teams make real-time pit-stop decisions via SSE telemetry.

## Commands

### Setup (one-time)
```bash
pip install -r requirements.txt
python scripts/dev/init_sqlite.py          # Create SQLite schema
python scripts/dev/build_it_vector_db.py   # Ingest KB into ChromaDB (requires Ollama)
```

### Tests
```bash
PYTHONPATH=. pytest tests/                 # Full test suite (no Ollama needed — LLM is mocked)
PYTHONPATH=. pytest tests/test_maestro.py  # Single file
```

### Benchmarks (requires Ollama + Copilot proxy on localhost:4141)
```bash
# Start Copilot proxy first: npx copilot-api@latest start

# Main architectural comparison (LLM Unique vs Multi-Agents)
python scripts/benchmark/compare_architectures.py \
  --max-tickets 10 --zero-shot-model phi3:latest \
  --agent-model phi3:latest --judge-model gpt-4o

python src/benchmark/ab_test_llm.py
python src/benchmark/test-biais-position.py --max-tickets 10
python scripts/benchmark/validate_benchmark_output.py \
  --input data/outputs/benchmark/comparison_results.json

# Kaggle SAE (local exam + GPT judge)
python scripts/benchmark/run_local_kaggle_exam.py --judge-model gpt-4o
```

### MCP tools benchmark (requires MCP server running in another terminal)
```bash
python scripts/dev/run_mcp_server.py   # Terminal 1
python -m src.benchmark.mcp_tools      # Terminal 2
```

### Racing Arena
```bash
python scripts/racing/run_demo.py    # Standalone demo (no hub needed)
python scripts/racing/run_arena.py   # Full arena: Hub + 3 legacy teams in parallel processes
python scripts/racing/run_hub.py     # Hub only (localhost:8000)

# Adversarial arena (4 teams: A=zero-shot, B=ReAct, C=validated, Psi=attacker)
python -m src.racing.start_arena

# Monitor during adversarial run:
tail -f logs/arena/team_team_psi.log        # attacker activity
tail -f logs/arena/team_team_c_validated.log
curl http://localhost:8000/team/team_a_zero_shot/strategy  # WeakProxy
curl http://localhost:8000/race-history                    # full log
curl http://localhost:8000/results
# Security report written after race ends:
# data/outputs/benchmark/security_race_report.json
```

### Environment variables
| Variable | Effect |
|----------|--------|
| `BIBOPS_NON_INTERACTIVE=1` | Skip interactive feedback prompts |
| `BIBOPS_MAX_TICKETS=5` | Limit tickets processed in benchmarks |
| `BIBOPS_DEFAULT_FEEDBACK=2` | Default feedback choice in non-interactive mode |
| `BIBOPS_POSITION_MAX_TICKETS=2` | Default ticket count for position bias test |
| `COPILOT_API_URL` | Override Copilot proxy URL (default: `http://localhost:4141/v1`) |
| `A2A_USERNAME` / `A2A_PASSWORD` | Basic Auth for A2A agent evaluation |
| `PYTHONPATH=.` | Required when running scripts directly from repo root |

## Architecture

### Module layout
```
src/
  common/       — Project-wide constants and shared text utilities
  agent/        — IT support agent and tools
  benchmark/    — Benchmark pipelines and A/B testing
  llm_professor/ — Evaluation engine (judge, security, greenops, composite)
  racing/       — Distributed F1 racing arena
    hub/        — FastAPI server + race engine + RAG service
    team_client/ — LangGraph-based team agent (runs as separate process)
scripts/        — Thin wrappers that call src/ modules
data/
  inputs/benchmark/ — Input CSVs (tickets_scenario_1.csv, 40 tickets)
  databases/    — bibops.db (SQLite) + vectordb/ (ChromaDB)
  outputs/      — JSON benchmark results, PNG charts
  runtime/      — JSONL execution traces
tests/
  unit/         — Unit tests (no Ollama needed)
  unit/fixtures/ — Test fixture JSON files
```

### IT Support agent (`src/agent/`)

`maestro.py::lancer_agent()` is the core ReAct loop. It:
1. Calls `_call_llm()` which returns an `AgentDecision` Pydantic model (`tool`, `argument`, `final_answer`) via the Ollama OpenAI-compatible endpoint with JSON mode — no regex parsing
2. If `tool` is set, looks up the function in `outils_disponibles` and executes it under `ThreadPoolExecutor` with per-tool timeouts from `TOOL_POLICIES`
3. Injects the result back into `MemoCourTerme` and loops (max 5 iterations by default)
4. Returns `{"reponse_finale": str, "trace": MaestroRunTrace}` when `tool` is None

Keyword routing (`KEYWORD_ROUTING` dict) pre-selects the recommended tool from the ticket text before the first LLM call — this is a hint only, not a constraint.

The three tools in `tools.py`:
- `verifier_statut_serveur(nom)` — SQLite lookup, timeout 3s
- `chercher_dans_kb(requete)` — JSON KB search, timeout 5s, 1 retry
- `chercher_documentation_technique(requete)` — ChromaDB RAG, timeout 8s, 1 retry, `RAG_DISTANCE_MAX=1.2`

All tools share the frozen `ToolPolicy` dataclass and are exposed as MCP tools in `mcp_server.py`.

### Common utilities (`src/common/`)

- **`config.py`** — Project-wide constants: `COPILOT_BASE_URL`, `DEFAULT_JUDGE_MODEL`, `DEFAULT_AGENT_MODEL`, `DEFAULT_ZERO_SHOT_MODEL`, `MODEL_REQUEST_TIMEOUT_S`, `OLLAMA_OPTIONS`, `INPUT_CSV`, `OUTPUT_DIR`
- **`text.py`** — Shared text/response helpers: `charger_copilot_api_key()`, `_extraire_texte()`, `_extraire_json_depuis_texte()`, `_executer_avec_timeout()`, `extraire_texte_reponse()`, `extraire_compteurs_tokens()`, and error-classification helpers

`src/benchmark/_llm_utils.py` still holds `appeler_modele()` and duplicates some helpers — prefer importing shared utilities from `src.common.text` and `src.common.config` in new code.

### LLM access pattern

All LLM calls use **Ollama** for local models (`ollama.chat(model=..., messages=...)`) or **OpenAI-compatible API** via the Copilot proxy at `http://localhost:4141/v1` (for gpt-4o, gpt-4o-mini, gpt-4.1, claude-haiku-4.5). There is no direct Anthropic SDK usage — Claude models are accessed through the OpenAI-compatible endpoint.

Only GPT models work for Racing Arena teams — Claude models return `400 model_not_supported` from the proxy backend.

### Evaluation engine (`src/llm_professor/`)

Evaluation flows through `EvaluatorRegistry` which runs registered evaluators and merges results:
- `QualityEvaluator` wraps `LLMProfessor` (gpt-4o judge, 0-10 score + JSON justification)
- `SecurityLLMInspectorAdapter` runs rule-based security checks (PII, injection, toxicity, secrets)
- `CompositePolicy.evaluate()` aggregates: quality×0.40 + security×0.35 + finops×0.10 + latency×0.10 + greenops×0.05 → score/100 + PASS/FAIL verdict (gate: quality ≥ 7, security ≥ 6)

`GreenOps.calculate_carbon_footprint(tokens, hardware_type)` estimates CO₂ from token counts.

Two scoring systems in separate files:
- **`llm_judge.py`** — `LLMProfessor`: LLM judge via Copilot proxy (gpt-4o), returns 0-10 score + JSON justification
- **`rule_engine.py`** — `EvaluationEngine`: pure rule-based scoring (no LLM)

### Racing Arena (`src/racing/`)

**Hub** (`hub/server.py`): FastAPI app started by `python -m src.racing.hub.server`. The `RaceEngine` runs as a background asyncio task (50 laps, 3s/lap) and pushes telemetry JSON to all connected SSE clients via `asyncio.Queue`.

**Teams** (`team_client/main.py`): Each team is a separate OS process launched by `start_arena.py`. It connects to Hub SSE, deserializes telemetry into `RacingState`, invokes the compiled LangGraph, and POSTs the `FinalDecision` (Pydantic-constrained `Literal["PIT_STOP", "STAY_OUT"]`) back to `/decision/{team_id}`.

**LangGraph graph** (`racing/graph.py`): Supervisor → conditional routing to tire/fuel/race engineer nodes → back to Supervisor → END. Each expert node is a separate `ChatOpenAI` call with structured output.

### Key data contracts

- `lancer_agent()` returns `dict` with keys `reponse_finale`, `trace` (serializable `MaestroRunTrace`)
- `MaestroRunTrace` is written as JSONL to `data/runtime/maestro/maestro_runs.jsonl`
- Benchmark outputs follow the schema validated by `validate_benchmark_output.py` (keys: `schema_version`, `config`, `summary`, `quality`, `security`, `composite`, `details`)
- RAG collections in ChromaDB are keyed as `KB{id}` and `DOC_{name}`
- SQLite database (`bibops.db`) is used ONLY for the `serveurs_it` table (server status data)

### Benchmark utilities (`src/benchmark/`)

`_llm_utils.py` holds benchmark-specific helpers like `appeler_modele()`. For new code, import shared utilities from `src.common.text` and `src.common.config` instead of `_llm_utils`.

### Tests

Tests patch `_call_llm` in `src/agent/maestro.py` directly — the mock returns `AgentDecision` objects without any network call. `make_fake_llm(decisions)` in `test_maestro.py` feeds a list of `AgentDecision` objects one per turn. Use this same pattern for any new agent tests.
