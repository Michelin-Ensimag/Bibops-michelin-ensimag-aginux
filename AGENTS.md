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
bibops dev init-db                         # Create SQLite schema
bibops dev build-vectordb                  # Ingest KB into ChromaDB (requires Ollama)
```

### Tests
```bash
bibops test all                              # Full test suite (no Ollama needed — LLM is mocked)
bibops test unit tests/unit/test_maestro.py  # Single file
```

### CLI (`bibops` — installed via `pip install -e .`)
```bash
bibops --help                                 # Top-level command tree

# Benchmarks (requires Ollama + Copilot proxy: npx copilot-api@latest start)
bibops bench compare-archs --max-tickets 10 --zero-shot-provider ollama --zero-shot-model phi3:latest --agent-provider ollama --agent-model phi3:latest --agent-max-iterations 3 --judge-model gpt-4o
bibops bench core mistral:latest
bibops bench ab-test --mode llm
bibops bench position-bias --max-tickets 10
bibops bench validate --input data/outputs/benchmark/comparison_results.json
bibops bench kaggle --agent-provider ollama --agent-model mistral:latest --judge-model gpt-4o

# Model/provider config
bibops config models
bibops config show
bibops config check --judge-model gpt-5.2 --agent-provider copilot --agent-model gpt-5.2

# Evaluation
bibops eval pending --db data/databases/bibops.db
bibops eval process --input data/inputs/benchmark/tickets_evalues_fake.json

# Dev tools
bibops dev init-db
bibops dev build-vectordb
bibops dev mcp-server
bibops dev coverage-gates

# Copilot tools
bibops copilot smoke-test
bibops copilot agent-mcp

# Tests
bibops test unit
bibops test all
bibops test coverage

# Report charts
bibops report charts

# Racing Arena
bibops racing demo            # Standalone demo (no hub needed)
bibops racing arena           # Hub + teams in parallel processes
bibops racing adversarial     # 4 teams: A=zero-shot, B=ReAct, C=validated, Psi=attacker
```

### Direct module fallback (PYTHONPATH=. required)
```bash
# MCP benchmark (requires MCP server in another terminal)
PYTHONPATH=. python -m src.agent.mcp_server         # Terminal 1
PYTHONPATH=. python -m src.bibops.benchmark.mcp_tools  # Terminal 2
```

### Racing Arena monitoring
```bash
tail -f logs/arena/team_team_psi.log             # attacker activity
curl http://localhost:8000/race-history           # full log
curl http://localhost:8000/results
# Security report: data/outputs/benchmark/security_race_report.json
```

### Environment variables
| Variable | Effect |
|----------|--------|
| `BIBOPS_NON_INTERACTIVE=1` | Skip interactive feedback prompts |
| `BIBOPS_JUDGE_MODEL` | Default Copilot/OpenAI-compatible judge model (default `gpt-4o`) |
| `BIBOPS_AGENT_PROVIDER` | Default agent provider: `ollama` or `copilot` |
| `BIBOPS_AGENT_MODEL` | Default multi-agent model (default `phi3:latest`) |
| `BIBOPS_ZERO_SHOT_PROVIDER` | Default zero-shot provider: `ollama` or `copilot` |
| `BIBOPS_ZERO_SHOT_MODEL` | Default zero-shot model (default `phi3:latest`) |
| `EVAL_BANK_AGENT_PROVIDER` | Optional provider override for integration evaluation suites |
| `BIBOPS_MAX_TICKETS=5` | Limit tickets processed in benchmarks |
| `BIBOPS_DEFAULT_FEEDBACK=2` | Default feedback choice in non-interactive mode |
| `BIBOPS_POSITION_MAX_TICKETS=2` | Default ticket count for position bias test |
| `COPILOT_API_URL` | Override Copilot proxy URL (default: `http://localhost:4141/v1`) |
| `A2A_USERNAME` / `A2A_PASSWORD` | Basic Auth for A2A agent evaluation |
| `PYTHONPATH=.` | Required when running Python modules directly from repo root |

## Architecture

### Module layout
```
src/
  bibops/           — Production namespace package
    cli/            — Typer CLI (main.py, commands/{bench,eval,dev,racing,copilot,test,config,report}.py)
    benchmark/      — CLI-backed benchmark runners formerly hosted in scripts/
    copilot/        — Copilot proxy smoke tests
    dev/            — Developer utilities such as coverage gates
    evaluation/     — Evaluation engine
      judges/       — llm_judge.py (LLMJudge, JudgeVerdict) + llm_professor.py (LLMProfessor) + rule_engine.py
      metrics/      — composite.py, greenops.py, consistency.py
      scoring/      — thresholds.py (ScoreThreshold, ScoreVerdict, load_thresholds, evaluate_score)
      reporting/    — regression.py
      checks.py     — PII, injection, secrets, toxicity, URL, refusal detectors
    adapters/       — Agent adapters (registry, it_support, a2a_client, openai_compat)
    probes/         — Probe loader (load_probes, list_categories, Probe schema)
    reporting/      — Report chart generator (`bibops report charts`)
    research/       — Experimental code (excluded from coverage gates)
  agent/            — IT support ReAct agent (maestro.py, tools.py, mcp_server.py, rag.py)
  common/           — Shared constants (config.py), provider-aware chat calls (chat_models.py), text helpers (text.py), LLM clients (llm_clients.py)
  racing/           — Distributed F1 racing arena
    hub/            — FastAPI server + race engine + RAG service
    team_client/    — LangGraph-based team agent (runs as separate process)
data/
  inputs/benchmark/ — Input CSVs (tickets_scenario_1.csv, 40 tickets)
  databases/        — bibops.db (SQLite) + vectordb/ (ChromaDB)
  outputs/          — JSON benchmark results, PNG charts
  runtime/          — JSONL execution traces
tests/
  unit/             — Unit tests (no Ollama needed)
  unit/fixtures/    — Test fixture JSON files
  _fakes/           — Shared test fakes (FakeOpenAI, make_response)
```

### IT Support agent (`src/agent/`)

`maestro.py::lancer_agent()` is the core ReAct loop. It:
1. Calls `_call_llm()` which returns an `AgentDecision` Pydantic model (`tool`, `argument`, `final_answer`) through the configured provider (`ollama` or `copilot`) with JSON mode — no regex parsing
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

- **`config.py`** — Project-wide constants: `COPILOT_BASE_URL`, supported providers/models, `DEFAULT_JUDGE_MODEL`, `DEFAULT_AGENT_PROVIDER`, `DEFAULT_AGENT_MODEL`, `DEFAULT_ZERO_SHOT_PROVIDER`, `DEFAULT_ZERO_SHOT_MODEL`, `MODEL_REQUEST_TIMEOUT_S`, `OLLAMA_OPTIONS`, `INPUT_CSV`, `OUTPUT_DIR`
- **`chat_models.py`** — Provider-aware `call_chat_model(provider, model, messages, ...)` abstraction for Ollama and Copilot/OpenAI-compatible chat calls
- **`text.py`** — Shared text/response helpers: `charger_copilot_api_key()`, `extraire_texte_reponse()`, `extraire_compteurs_tokens()`, and error-classification helpers
- **`llm_clients.py`** — Singleton `get_copilot_client()` (OpenAI-compatible), `is_copilot_available()` (TCP probe)

Benchmark runners live under `src/bibops/benchmark/`; prefer importing shared utilities from `src.common.text` and `src.common.config` in new code.

### LLM access pattern

LLM calls use an explicit provider/model pair. Local chat models use **Ollama** (`provider=ollama`, e.g. `phi3:latest`, `mistral:latest`). Remote chat and judge models use the **OpenAI-compatible API** via the Copilot proxy at `http://localhost:4141/v1` (`provider=copilot`, e.g. `gpt-4o`, `gpt-5.2`, `claude-haiku-4.5`, Gemini/Grok proxy models). There is no direct Anthropic SDK usage — Claude models are accessed through the OpenAI-compatible endpoint.

Only GPT models work for Racing Arena teams — Claude models return `400 model_not_supported` from the proxy backend.

### Evaluation engine (`src/bibops/evaluation/`)

Evaluation flows through `EvaluatorRegistry` which runs registered evaluators and merges results:
- `QualityEvaluator` wraps `LLMProfessor` — uses `LLMJudge` internally (raw OpenAI, no LangChain); returns 0-10 score + justification, persists to SQLite
- `SecurityLLMInspectorAdapter` runs rule-based security checks (PII, injection, toxicity, secrets)
- `CompositePolicy.evaluate()` aggregates: quality×0.40 + security×0.35 + finops×0.10 + latency×0.10 + greenops×0.05 → score/100 + PASS/FAIL verdict (gate: quality ≥ 7, security ≥ 6)

Two judge classes, different roles:
- **`LLMJudge`** (`judges/llm_judge.py`) — general-purpose scoring primitive: `score(criterion, question, answer)` → `JudgeVerdict(score: float, justification: str)`. Used by integration tests.
- **`LLMProfessor`** (`judges/llm_professor.py`) — IT-support-specific wrapper around `LLMJudge`: adds RCA context, SQLite persistence, batch evaluation (`evaluer_tickets_en_attente`). Used by benchmark scripts.

`EvaluationEngine` (`judges/rule_engine.py`) — pure rule-based scoring (no LLM): error/feedback/speed/token/F1 dimensions.

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

### Tests

Tests patch `_call_llm` in `src/agent/maestro.py` directly — the mock returns `AgentDecision` objects without any network call. `make_fake_llm(decisions)` in `test_maestro.py` feeds a list of `AgentDecision` objects one per turn. Use this same pattern for any new agent tests.

`tests/_fakes/fake_openai.py` provides `FakeOpenAI` and `make_response()` for tests that need a mock OpenAI client (LLMJudge, LLMProfessor).
