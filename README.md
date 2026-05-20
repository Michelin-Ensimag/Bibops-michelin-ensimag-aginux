# BibOps

> A reproducible evaluation harness for LLM-based IT support — pitting a **zero-shot assistant** against a **tool-using ReAct agent**, scoring both on quality, safety, cost, latency and carbon, and stress-testing them in a live **multi-agent Racing Arena**.

[![Pipeline CI/CD BibOps](https://github.com/Michelin-Ensimag/BibOps-michelin-ensimag-aginux/actions/workflows/ci.yml/badge.svg)](https://github.com/Michelin-Ensimag/BibOps-michelin-ensimag-aginux/actions/workflows/ci.yml)

BibOps was built for the Michelin × Ensimag _Aginux_ project. It treats "does this LLM make a good IT support agent?" as a measurable engineering question — not a vibe check.

## Why BibOps

- **Two architectures, one bench.** Run the same 40 tickets through `LLM Unique` (zero-shot, no tools) and `Système Multi-Agents` (ReAct loop + KB search + RAG + server-status tool) and get a side-by-side scorecard.
- **RAGAS-inspired adversarial loop.** `bench adversarial` iterates a probe set against both architectures until convergence, surfacing where each one breaks.
- **A live multi-agent stress test.** The Racing Arena runs 3–4 LLM-powered F1 teams as separate processes against a FastAPI hub streaming telemetry over SSE — including an attacker team (Ψ) that probes the others.
- **Composite scoring with hard gates.** Every answer is rolled up into quality 0.40 / security 0.35 / finops 0.10 / latency 0.10 / greenops 0.05, with PASS requiring quality ≥ 7 and security ≥ 6.

## Architecture at a glance

```
                  ┌─────────────────────────────┐
                  │  IT support tickets (CSV)   │
                  └──────────────┬──────────────┘
                                 │
              ┌──────────────────┴──────────────────┐
              ▼                                     ▼
     ┌─────────────────┐                  ┌──────────────────┐
     │   LLM Unique    │                  │  ReAct Agent     │
     │   (zero-shot)   │                  │  + KB / RAG /    │
     │                 │                  │   server tools   │
     └────────┬────────┘                  └────────┬─────────┘
              │                                     │
              └─────────────────┬───────────────────┘
                                ▼
                    ┌───────────────────────┐
                    │  LLMJudge + rules     │
                    │  quality • security   │
                    │   finops • latency    │
                    │       greenops        │
                    └──────────┬────────────┘
                               ▼
                    Composite score / PASS · FAIL

   Racing Arena (independent experiment)

   ┌────────────┐   SSE telemetry    ┌──────────────────────┐
   │  Race Hub  │ ─────────────────▶ │  Team A · B · C · Ψ  │
   │  (FastAPI) │ ◀──── decisions ── │  (LangGraph procs)   │
   └────────────┘                    └──────────────────────┘
```

## Quickstart

```bash
pip install -r requirements.txt
pip install -e .                  # exposes the `bibops` CLI
bibops --help
```

Initialise local data stores (SQLite + ChromaDB). The vector store needs Ollama running for embeddings; unit tests do not.

```bash
bibops dev init-db
bibops dev build-vectordb
```

30-second smoke test — no Ollama required:

```bash
bibops racing demo                # single-team racing demo
bibops test unit                  # mocked-LLM unit suite
```

Full architecture comparison (needs Ollama for local models and the Copilot proxy for the judge):

```bash
bibops bench compare-archs \
  --max-tickets 10 \
  --zero-shot-provider ollama --zero-shot-model phi3:latest \
  --agent-provider     ollama --agent-model     phi3:latest \
  --agent-max-iterations 3 \
  --judge-model gpt-4o
```

Results land in `data/outputs/benchmark/comparison_results.json`; charts via `bibops report charts`.

## The two flagship experiments

### `bench compare-archs` — head-to-head benchmark

Streams each ticket through both architectures, asks the LLM judge to score both answers (with `bench position-bias` available to detect order-dependent grading), and writes a schema-validated JSON report. The agent uses three tools: `verifier_statut_serveur` (SQLite), `chercher_dans_kb` (JSON KB), and `chercher_documentation_technique` (ChromaDB RAG).

### `racing adversarial` — multi-agent live arena

Four teams run as independent processes against the FastAPI hub: **A** (zero-shot), **B** (ReAct), **C** (validated/guarded), and **Ψ** (attacker probing the others). The hub streams 15 laps of telemetry (10 s/lap, after an 8 s warm-up) over SSE; each team's LangGraph supervisor routes to tire / fuel / race-engineer experts and POSTs a `Literal["PIT_STOP", "STAY_OUT"]` back. The full security report is written to `data/outputs/benchmark/security_race_report.json`.

```bash
bibops racing adversarial
tail -f logs/arena/team_team_psi.log
curl http://localhost:8000/race-history
```

## CLI reference

All commands are exposed under the `bibops` entry point — no `PYTHONPATH` needed.

| Group | Command | Purpose |
| --- | --- | --- |
| `bench` | `compare-archs` | LLM Unique vs Multi-Agents head-to-head |
| | `ab-test` | A/B test between two models or agents |
| | `position-bias` | Detect order-dependent judge bias |
| | `adversarial` | RAGAS-inspired convergence loop (10 tickets × N iter) |
| | `adversarial-demo` | Single-ticket adversarial demo (VPN-China) |
| | `kaggle` | Local Kaggle SAE exam, judge-scored |
| | `mcp-tools` | MCP tools benchmark (needs `dev mcp-server` running) |
| | `a2a` | Evaluate external A2A agents with basic auth |
| | `core` | Legacy local Ollama benchmark |
| | `validate` | Validate a benchmark JSON against the schema |
| `eval` | `pending` | Score pending rows in the SQLite `evaluations` table |
| | `process` | Rule-engine-score a JSON file of ticket responses |
| | `suite` | Integration suites: `all` / `security` / `quality` / `robustness` / `tool_use` / `regression` |
| `racing` | `demo` | Standalone single-team demo (no hub) |
| | `hub` | Start hub only on `localhost:8000` |
| | `arena` | Full arena: hub + 3 legacy teams |
| | `adversarial` | 4-team adversarial arena (A / B / C / Ψ) |
| `dev` | `init-db` | Create the SQLite schema |
| | `build-vectordb` | Ingest the KB into ChromaDB (needs Ollama) |
| | `mcp-server` | Run the MCP tool server (stdio) |
| | `coverage-gates` | Enforce coverage gates from `coverage.json` |
| `copilot` | `smoke-test` | Ping the configured Copilot proxy models |
| | `agent-mcp` | Copilot + MCP multi-model benchmark |
| `test` | `unit` / `integration` / `all` / `coverage` | Pytest runners with sensible defaults |
| `config` | `show` / `models` / `check` | Inspect or validate the active provider/model setup |
| `report` | `charts` | Regenerate PNG charts under `data/outputs/benchmark/charts/` |

## Evaluation pipeline

Each answer flows through:

1. **Probes** — categorised IT-support inputs loaded from `BIBOPS_PROBES_DIR` via `src/bibops/probes/`.
2. **Judges** — `LLMJudge` (general primitive, raw OpenAI client) and `LLMProfessor` (IT-support wrapper with RCA context and SQLite persistence), plus the rule-based `EvaluationEngine` for error / feedback / speed / token / F1 dimensions.
3. **Checks** — PII, prompt injection, secrets, toxicity, URL and refusal detectors from `src/bibops/evaluation/checks.py`.
4. **Composite scoring** — weighted aggregation with hard gates, thresholds loaded from `BIBOPS_THRESHOLDS_DIR` via `evaluation/scoring/thresholds.py`.

## External services

| Service | When you need it | Start command |
| --- | --- | --- |
| **Ollama** | Local models (`phi3`, `mistral`, …) and KB embeddings | run the Ollama daemon |
| **Copilot proxy** | OpenAI-compatible judge + GPT/Claude-via-proxy models | `npx copilot-api@latest start` |
| **A2A endpoints** | `bench a2a` only | external; supply credentials via env |

Default proxy URL: `http://localhost:4141/v1`. Only GPT models work for Racing Arena teams — the proxy returns `400 model_not_supported` for Claude.

## Configuration

| Variable | Purpose | Default |
| --- | --- | --- |
| `BIBOPS_JUDGE_MODEL` | Judge model used by evaluation flows | `gpt-4o` |
| `BIBOPS_AGENT_PROVIDER` / `BIBOPS_AGENT_MODEL` | Multi-agent provider/model | `ollama` / `phi3:latest` |
| `BIBOPS_ZERO_SHOT_PROVIDER` / `BIBOPS_ZERO_SHOT_MODEL` | Zero-shot provider/model | `ollama` / `phi3:latest` |
| `BIBOPS_PROBES_DIR` | Override probe directory | bundled |
| `BIBOPS_THRESHOLDS_DIR` | Override threshold profiles | bundled |
| `BIBOPS_MAX_TICKETS` | Cap tickets processed in benchmarks | unset |
| `BIBOPS_POSITION_MAX_TICKETS` | Cap for position-bias test | unset |
| `BIBOPS_NON_INTERACTIVE` / `BIBOPS_DEFAULT_FEEDBACK` | Run scripts without prompts | unset / `2` |
| `BIBOPS_MODEL_REQUEST_TIMEOUT_S` / `BIBOPS_JUDGE_REQUEST_TIMEOUT_S` | Per-call timeouts | from `config.py` |
| `BIBOPS_PSI_TARGETING` / `BIBOPS_PSI_MIN_BALANCED_PROBES` | Tune the Ψ attacker | defaults in code |
| `BIBOPS_RACING_HUB_URL` | Override Racing Hub URL | `http://localhost:8000` |
| `COPILOT_API_URL` / `COPILOT_BASE_URL` | OpenAI-compatible proxy URL | `http://localhost:4141/v1` |
| `COPILOT_API_KEY` / `COPILOT_AGENT_MODELS` | Proxy auth and model allowlist | unset |
| `A2A_URL` / `A2A_USERNAME` / `A2A_PASSWORD` | External A2A endpoint | unset |
| `A2A_FACTCHECKER_URL` / `_USERNAME` / `_PASSWORD` | A2A factchecker variant | unset |

## Repository layout

```text
src/
  agent/            IT-support ReAct agent, tools, MCP server, RAG
  bibops/
    cli/            Typer commands (bench, eval, dev, racing, …)
    evaluation/
      judges/       LLMJudge, LLMProfessor, rule engine, discriminator
      metrics/      composite, greenops, consistency
      scoring/      thresholds, verdicts
      reporting/    regression vs frozen baselines
      checks.py     PII / injection / secrets / toxicity / URL / refusal
    probes/         Probe loader and schema
    benchmark/      Benchmark pipelines
    adapters/       Agent adapters (registry, it_support, a2a, openai_compat)
  common/           Shared config, model clients, text helpers
  racing/
    hub/            FastAPI server + race engine + RAG service
    team_client/    LangGraph team agent (one OS process per team)
data/
  inputs/           Benchmark tickets and probe inputs
  databases/        SQLite (`bibops.db`) and Chroma vector DB
  outputs/          Benchmark JSON outputs and PNG charts
  runtime/          JSONL execution traces (e.g. `maestro_runs.jsonl`)
tests/
  unit/             Unit tests with mocked LLM calls (no Ollama needed)
  _fakes/           Shared OpenAI-compatible test fakes
```

## Outputs and artefacts

| Path | Description |
| --- | --- |
| `data/outputs/benchmark/comparison_results.json` | Architecture comparison output |
| `data/outputs/benchmark/charts/` | Generated benchmark charts |
| `data/outputs/benchmark/security_race_report.json` | Racing Arena adversarial report |
| `data/runtime/maestro/maestro_runs.jsonl` | ReAct agent JSONL trace |
| `data/databases/bibops.db` | SQLite server-status database |
| `data/databases/vectordb/` | Chroma vector database for RAG |
| `logs/arena/team_*.log` | Per-team Racing Arena logs |

## Development

```bash
bibops test unit             # mocked-LLM unit suite
bibops test all              # full suite
bibops test coverage         # writes coverage.json
bibops dev coverage-gates    # enforce gates against coverage.json
ruff check .                 # lint
```

Tests patch `_call_llm` in `src/agent/maestro.py` directly — the mock returns `AgentDecision` Pydantic objects with no network call. `make_fake_llm(decisions)` in `tests/unit/test_maestro.py` feeds one decision per turn; use the same pattern for new agent tests. `tests/_fakes/fake_openai.py` provides `FakeOpenAI` and `make_response()` for judge tests.

## Further reading

- Complete CLI reference with every command, flag, and navigation guide: [docs/CLI_REFERENCE.md](docs/CLI_REFERENCE.md)
- Engineering reference for internals (agent loop, scoring formula, racing internals): [docs/BIBOPS_DETAILED.md](docs/BIBOPS_DETAILED.md)
- Project guidance for contributors and Claude Code: [CLAUDE.md](CLAUDE.md)
