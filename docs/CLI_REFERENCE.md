# BibOps CLI Reference

This file lists **every** `bibops` command, what it does, and how to chain commands into typical workflows. It is generated from the live CLI surface — to re-verify, run `bibops --help` and drill into any subcommand with `--help`.

If you only want the value proposition, read the [README](../README.md). For internals, see [BIBOPS_DETAILED](BIBOPS_DETAILED.md).

---

## How the CLI is organised

```
bibops
├── bench       Benchmarks (compare architectures, A/B, adversarial, MCP, A2A, Kaggle, validate)
├── eval        Evaluation (pending judge rows, JSON rule-scoring, integration suites)
├── racing      Racing Arena (demo, hub, full arena, adversarial 4-team mode)
├── dev         Developer utilities (init DB, build vector DB, MCP server, coverage gates)
├── copilot     Copilot-proxy utilities (smoke test, MCP multi-model benchmark)
├── test        Pytest runners (unit, integration, all, coverage)
├── config      Inspect / validate provider + model configuration
└── report      Generate report-ready artefacts (charts)
```

Every command is invoked as `bibops <group> <command> [OPTIONS]`. Get the next layer of help with `bibops <group> --help` or `bibops <group> <command> --help`.

---

## Navigation guide — "I want to…"

| Goal | Command |
| --- | --- |
| **Set up the project for the first time** | `bibops dev init-db && bibops dev build-vectordb` |
| **Run a quick smoke test, no Ollama** | `bibops racing demo` or `bibops test unit` |
| **Compare zero-shot vs ReAct on tickets** | `bibops bench compare-archs --max-tickets 10` |
| **A/B two models with a judge** | `bibops bench ab-test --mode llm` |
| **Detect order bias in the judge** | `bibops bench position-bias --max-tickets 10` |
| **Run the adversarial convergence loop** | `bibops bench adversarial --max-iter 3` |
| **Demo one adversarial ticket** | `bibops bench adversarial-demo` |
| **Benchmark MCP-exposed tools** | `bibops dev mcp-server` (T1), then `bibops bench mcp-tools` (T2) |
| **Score an external A2A agent** | `bibops bench a2a --agents https://… --username … --password …` |
| **Validate a benchmark output JSON** | `bibops bench validate --input data/outputs/benchmark/comparison_results.json` |
| **Score pending DB rows with the LLM judge** | `bibops eval pending --db data/databases/bibops.db` |
| **Rule-score a JSON of ticket responses** | `bibops eval process --input <file>.json` |
| **Run only the security probe suite** | `bibops eval suite security` |
| **Start the Racing Arena** | `bibops racing arena` or `bibops racing adversarial` |
| **Just start the racing hub** | `bibops racing hub` |
| **See the active model/provider defaults** | `bibops config show` |
| **List supported providers/models** | `bibops config models` |
| **Validate a specific model combo before running** | `bibops config check --judge-model gpt-4o …` |
| **Regenerate PNG charts after a benchmark** | `bibops report charts` |
| **Ping the Copilot proxy** | `bibops copilot smoke-test` |
| **Run the Copilot + MCP multi-model benchmark** | `bibops copilot agent-mcp` |
| **Run the test suite** | `bibops test unit` / `bibops test all` |
| **Get coverage JSON + enforce gates** | `bibops test coverage && bibops dev coverage-gates` |

---

## `bibops bench` — benchmarks

Many `bench` subcommands are **pass-throughs** to argparse-based scripts under `src/bibops/benchmark/`. Their `--help` shows the internal `---module-attr` / `---label` plumbing; the **real** flags accepted are listed below.

### `bench compare-archs`

LLM Unique (zero-shot) vs Système Multi-Agents (ReAct) on the same ticket set.

| Flag | Default | Notes |
| --- | --- | --- |
| `--input-csv PATH` | bundled `tickets_scenario_1.csv` | CSV with `id, contexte, ticket` |
| `--max-tickets N` | all | Cap tickets processed |
| `--domain {all,…}` | `all` | Filter tickets by domain before `--max-tickets` |
| `--zero-shot-provider {ollama,copilot}` | `ollama` | |
| `--zero-shot-model TEXT` | `phi3:latest` | |
| `--agent-provider {ollama,copilot}` | `ollama` | |
| `--agent-model TEXT` | `phi3:latest` | |
| `--agent-max-iterations N` | `3` | ReAct loop cap |
| `--judge-model TEXT` | `gpt-4o` | Routed through Copilot proxy |
| `--db-path PATH` | `data/databases/bibops.db` | Required by `LLMProfessor` |
| `--hardware-type {local,cloud}` | `local` | For carbon estimation |
| `--output-json PATH` | `data/outputs/benchmark/comparison_results.json` | |

**Example.** Full Ollama run, 10 tickets, GPT-4o judge:

```bash
bibops bench compare-archs \
  --max-tickets 10 \
  --zero-shot-provider ollama --zero-shot-model phi3:latest \
  --agent-provider     ollama --agent-model     phi3:latest \
  --agent-max-iterations 3 \
  --judge-model gpt-4o
```

### `bench ab-test`

A/B test between two models. The `--mode` flag selects the underlying script.

| Mode | Script | Use it for |
| --- | --- | --- |
| `llm` (default) | `ab_test_llm` | Judge-scored comparison |
| `user` | `ab_test_user` | Human-in-the-loop comparison |
| `statements` | `ab_test_llm_statements` | Factchecker vs BibOps on statements |

LLM-mode flags (from `ab_test_llm.py`): `--model-a`, `--model-b`, `--judge-model`, `--output`, `--max-tickets`, `--inter-ticket-delay`. The last two also honor `BIBOPS_AB_LLM_MAX_TICKETS` and `BIBOPS_AB_LLM_INTER_TICKET_DELAY`.

```bash
bibops bench ab-test --mode llm \
  --model-a phi3:latest --model-b mistral:latest \
  --judge-model gpt-4o --max-tickets 10
```

### `bench position-bias`

Detect order-dependent grading by the judge.

| Mode | Use it for |
| --- | --- |
| `tickets` (default) | CSV ticket scenarios |
| `statements` | Factchecker pairs |

Flags: `--model-a`, `--model-b`, `--judge-model`, `--max-tickets`, `--seed`, `--output`.

```bash
bibops bench position-bias --max-tickets 10 --seed 42
```

### `bench adversarial`

RAGAS-inspired convergence loop: ReAct + RAG vs zero-shot, replayed `N` iterations per ticket.

Flags: `--max-tickets`, `--max-iter` (default `2`), `--generator-model` (default `gpt-4o-mini`), `--generator-provider {copilot,ollama}`, `--judge-model` (default `gpt-4o`), `--quiet`, `--dataset PATH`, `--output-json PATH`, `--output-chart PATH`.

```bash
bibops bench adversarial --max-tickets 10 --max-iter 3
```

Outputs:
- `data/outputs/benchmark/adversarial_convergence.json`
- `data/outputs/benchmark/charts/adversarial_convergence.png`

### `bench adversarial-demo`

Single-ticket demo of the same loop. Default scenario: VPN-China.

```bash
bibops bench adversarial-demo --mode react
```

### `bench mcp-tools`

Benchmark the IT-support tools exposed over MCP. Requires the MCP server in another terminal:

```bash
# Terminal 1
bibops dev mcp-server
# Terminal 2
bibops bench mcp-tools
```

### `bench a2a`

Evaluate one or more external A2A-compatible agents over the BibOps probe set.

Common flags (from `compare_a2a_agents.py`):

| Flag | Default | Notes |
| --- | --- | --- |
| `--agents URL [URL …]` | bundled defaults | A2A base URLs |
| `--max-agents N` | none | Cap agents |
| `--probe-file PATH` | bundled | Custom probe suite JSON |
| `--max-probes N` | none | Cap probes per agent |
| `--username` / `--password` | `$A2A_USERNAME` / `$A2A_PASSWORD` | Basic Auth |
| `--timeout N` | `120` | JSON-RPC request timeout |
| `--discovery-timeout N` | `30` | Agent card timeout |
| `--max-retries N` | `2` | Retries for transient errors |
| `--retry-backoff-s F` | `1.0` | Initial retry backoff |
| `--use-streaming` | off | Also call `message/stream` for tool probes |
| `--stream-timeout N` | `120` | Streaming request timeout |
| `--no-model-probe` / `--no-identity-probe` | off | Skip identity self-report probe |
| `--no-kaggle` | off | Do not append Kaggle SAE probes |
| `--no-cache` / `--cache-file PATH` | off / bundled | Cache control |
| `--use-fact-checker` | off | Route through external A2A fact-checker |

```bash
bibops bench a2a \
  --agents https://example.com/a2a \
  --max-probes 5 \
  --username "$A2A_USERNAME" --password "$A2A_PASSWORD"
```

### `bench kaggle`

Local Kaggle SAE exam, judge-scored.

Flags: `--exam-file PATH`, `--judge-model`, `--agent-provider {ollama,copilot}`, `--agent-model`, `--max-questions`.

```bash
bibops bench kaggle --agent-provider ollama --agent-model mistral:latest --judge-model gpt-4o
```

### `bench core`

Legacy local-Ollama benchmark producing `tickets_evalues.json`. Kept for historical comparisons.

```bash
bibops bench core
```

### `bench validate`

Validate a benchmark JSON against the schema (`schema_version`, `config`, `summary`, `quality`, `security`, `composite`, `details`).

```bash
bibops bench validate --input data/outputs/benchmark/comparison_results.json
```

---

## `bibops eval` — evaluation

### `eval pending`

Score rows where `score IS NULL` in the SQLite `evaluations` table via `LLMProfessor`.

| Flag | Default |
| --- | --- |
| `--db PATH` | `data/databases/bibops.db` |
| `--judge-model` | `gpt-4o` |

```bash
bibops eval pending --db data/databases/bibops.db --judge-model gpt-4o
```

### `eval process`

Rule-engine-score a JSON file of ticket responses.

| Flag | Required | Notes |
| --- | --- | --- |
| `--input` / `-i` | ✓ | Input JSON of ticket responses |
| `--output` / `-o` | | Output JSON of scored tickets |

```bash
bibops eval process -i data/inputs/benchmark/tickets_evalues_fake.json
```

### `eval suite [CATEGORY]`

Run integration tests through pytest, scoped by category.

| Argument | Choices | Default |
| --- | --- | --- |
| `CATEGORY` | `all`, `security`, `quality`, `robustness`, `tool_use`, `regression` | `all` |

| Flag | Default | Notes |
| --- | --- | --- |
| `--adapter` | `it_support` | Adapter name passed to tests |
| `--model` | none | Optional agent-model override |
| `--agent-provider` / `--provider` | none | Override provider for `it_support` |
| `--judge-model` | `gpt-4o` | |
| `--threshold-profile` | `default` | Threshold profile |

```bash
bibops eval suite security --judge-model gpt-4o
```

---

## `bibops racing` — Racing Arena

| Command | Process layout | External deps |
| --- | --- | --- |
| `racing demo` | one process, no hub | none |
| `racing hub` | just the FastAPI hub on `localhost:8000` | none |
| `racing arena` | hub + 3 legacy team processes | Copilot proxy (GPT only) |
| `racing adversarial` | hub + 4 teams (A=zero-shot, B=ReAct, C=validated, Ψ=attacker) | Copilot proxy (GPT only) |

```bash
bibops racing adversarial
# Monitor:
tail -f logs/arena/team_team_psi.log
curl http://localhost:8000/race-history
curl http://localhost:8000/results
# Security report:
cat data/outputs/benchmark/security_race_report.json
```

Race defaults: 15 laps × 10 s/lap with an 8 s warm-up and 3-lap safety-car phases (see `RaceEngine` in `src/racing/hub/race_engine.py`).

---

## `bibops dev` — developer utilities

| Command | Purpose | Needs |
| --- | --- | --- |
| `dev init-db` | Create the SQLite schema (`serveurs_it`, KB metadata) | nothing |
| `dev build-vectordb` | Ingest the KB into ChromaDB | **Ollama** for embeddings |
| `dev mcp-server` | Run the MCP tool server (stdio transport) | nothing |
| `dev coverage-gates` | Enforce coverage gates against `coverage.json` | a prior `bibops test coverage` run |

```bash
bibops dev init-db
bibops dev build-vectordb
```

---

## `bibops copilot` — Copilot proxy utilities

| Command | Purpose |
| --- | --- |
| `copilot smoke-test` | Send one IT-support ticket to each configured Copilot proxy model and print results |
| `copilot agent-mcp` | Multi-model benchmark of Copilot models running through the MCP tool server |

Requires the proxy running: `npx copilot-api@latest start` (defaults to `http://localhost:4141/v1`).

```bash
bibops copilot smoke-test
bibops copilot agent-mcp
```

---

## `bibops test` — pytest runners

| Command | Equivalent | Use it for |
| --- | --- | --- |
| `test unit` | `pytest tests/unit` | Fast, mocked-LLM suite — no Ollama or proxy needed |
| `test integration` | `pytest tests/integration` (when present) | Live judge / adapter tests |
| `test all` | `pytest tests/` | Full suite |
| `test coverage` | `pytest --cov … --cov-report=json` | Writes `coverage.json` for gates |

You can still target individual pytest markers manually (declared in `pyproject.toml`):

```bash
pytest -m security
pytest -m "tool_use and not regression"
```

Markers: `security`, `quality`, `reasoning`, `tool_use`, `robustness`, `performance`, `regression`.

---

## `bibops config` — configuration introspection

| Command | Purpose |
| --- | --- |
| `config show` | Print active provider/model defaults after env-var overrides |
| `config models` | List supported providers and models |
| `config check` | Validate one provider/model combination before a long run |

```bash
bibops config show
bibops config check \
  --judge-model gpt-4o \
  --agent-provider ollama --agent-model phi3:latest \
  --zero-shot-provider ollama --zero-shot-model phi3:latest
```

---

## `bibops report` — reporting

### `report charts`

Regenerate PNG charts from benchmark outputs.

| Flag | Default |
| --- | --- |
| `--benchmark-dir PATH` | `data/outputs/benchmark/` |
| `--charts-dir PATH` | `data/outputs/benchmark/charts/` |
| `--coverage-json PATH` | `coverage.json` |
| `--eval-bank-dir PATH` | bundled |
| `--strict` | off — fail if an expected source JSON is missing |

```bash
bibops report charts --strict
```

---

## Common end-to-end workflows

### 1. Cold-start setup → first comparison

```bash
pip install -r requirements.txt
pip install -e .
bibops dev init-db
bibops dev build-vectordb                  # needs Ollama
bibops bench compare-archs --max-tickets 5
bibops bench validate --input data/outputs/benchmark/comparison_results.json
bibops report charts
```

### 2. Investigate a judge that may be biased

```bash
bibops bench position-bias --max-tickets 10
bibops bench ab-test --mode llm --max-tickets 10 --judge-model gpt-4o
```

### 3. Stress-test agents against probes

```bash
bibops eval suite security
bibops eval suite tool_use
bibops bench adversarial --max-tickets 10 --max-iter 3
```

### 4. Run the multi-agent racing experiment

```bash
# In one terminal:
bibops racing adversarial
# In another:
tail -f logs/arena/team_team_psi.log
curl -s http://localhost:8000/race-history | jq .
```

### 5. Quality-gate a CI build

```bash
bibops test coverage
bibops dev coverage-gates
bibops bench compare-archs --max-tickets 3 --judge-model gpt-4o-mini
bibops bench validate --input data/outputs/benchmark/comparison_results.json
```

---

## Tips

- **No `PYTHONPATH=.` required** for the installed `bibops` entry point. Only use it for raw `python -m src.<module>` invocations.
- **Pass-through commands** (`bench compare-archs`, `core`, `kaggle`, `a2a`, `validate`, `adversarial`, `adversarial-demo`) accept any flag the underlying argparse script defines, even though `--help` only shows the wrapper plumbing. Read the relevant `src/bibops/benchmark/<module>.py` for the canonical flag list.
- **Env vars override defaults**. Set `BIBOPS_JUDGE_MODEL`, `BIBOPS_AGENT_PROVIDER`, `BIBOPS_MAX_TICKETS`, etc. before running. Full table in the [README](../README.md#configuration).
- **`config check` first.** A misconfigured model fails fast there rather than 5 minutes into a benchmark.
- **`bench validate` is cheap.** Run it after any benchmark to catch schema regressions immediately.
- **Two-terminal commands.** `bench mcp-tools` needs `dev mcp-server` running; the racing modes all need the Copilot proxy when teams use GPT models.
