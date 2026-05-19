# BibOps

BibOps is an LLM evaluation and agent benchmarking framework built for Michelin IT support scenarios. It compares a simple zero-shot assistant against a tool-using ReAct agent, scores the results across quality and safety dimensions, and includes a Racing Arena for distributed multi-agent decision experiments.

[![Pipeline CI/CD BibOps](https://github.com/Michelin-Ensimag/BibOps-michelin-ensimag-aginux/actions/workflows/ci.yml/badge.svg)](https://github.com/Michelin-Ensimag/BibOps-michelin-ensimag-aginux/actions/workflows/ci.yml)

## What BibOps Does

- Compares two support architectures: **LLM Unique** and **Systeme Multi-Agents**.
- Runs reproducible benchmarks over IT support tickets.
- Evaluates answers with quality, security, latency, cost, and greenops metrics.
- Exposes support tools through MCP for agent experiments.
- Tests external A2A agents with authenticated endpoints.
- Runs a Racing Arena where LLM-powered F1 teams make live pit-stop decisions.

For the full architecture, use cases, evaluation policy, and command reference, see [docs/BIBOPS_DETAILED.md](docs/BIBOPS_DETAILED.md).

## Repository Layout

```text
src/
  agent/            IT support ReAct agent, tools, MCP server, RAG
  bibops/           CLI, benchmarks, evaluation, adapters, reporting
  common/           Shared config, model clients, text helpers
  racing/           Racing Arena hub and team clients
data/
  inputs/           Benchmark tickets and probe inputs
  databases/        SQLite database and Chroma vector database
  outputs/          Benchmark JSON outputs and generated charts
  runtime/          Execution traces
tests/
  unit/             Unit tests with mocked LLM calls
  _fakes/           Shared OpenAI-compatible test fakes
```

## Quick Start

Install the project:

```bash
pip install -r requirements.txt
pip install -e .
bibops --help
```

Initialize local data stores:

```bash
bibops dev init-db
bibops dev build-vectordb
```

`build-vectordb` uses Ollama embeddings. Unit tests do not require Ollama or network access.

## Common Workflows

Run tests:

```bash
bibops test unit
bibops test all
bibops test coverage
bibops dev coverage-gates
```

Inspect model/provider configuration:

```bash
bibops config show
bibops config models
bibops config check --judge-model gpt-4o --agent-provider ollama --agent-model phi3:latest
```

Compare the zero-shot and multi-agent architectures:

```bash
bibops bench compare-archs \
  --max-tickets 10 \
  --zero-shot-provider ollama \
  --zero-shot-model phi3:latest \
  --agent-provider ollama \
  --agent-model phi3:latest \
  --agent-max-iterations 3 \
  --judge-model gpt-4o
```

Evaluate prepared answers or an existing evaluation database:

```bash
bibops eval pending --db data/databases/bibops.db
bibops eval process --input data/inputs/benchmark/tickets_evalues_fake.json
bibops eval suite security
```

Generate benchmark charts:

```bash
bibops report charts
```

Run Racing Arena modes:

```bash
bibops racing demo
bibops racing arena
bibops racing adversarial
```

## External Services

Some workflows need local or remote model services:

- **Ollama**: required for local models such as `phi3:latest` or `mistral:latest`, and for vector database ingestion.
- **Copilot proxy**: required for OpenAI-compatible judge and remote model calls.

Start the proxy when needed:

```bash
npx copilot-api@latest start
```

The default proxy URL is `http://localhost:4141/v1`.

## Configuration

| Variable | Purpose | Default |
| --- | --- | --- |
| `BIBOPS_JUDGE_MODEL` | Judge model used by evaluation flows | `gpt-4o` |
| `BIBOPS_AGENT_PROVIDER` | Multi-agent provider | `ollama` |
| `BIBOPS_AGENT_MODEL` | Multi-agent model | `phi3:latest` |
| `BIBOPS_ZERO_SHOT_PROVIDER` | Zero-shot provider | `ollama` |
| `BIBOPS_ZERO_SHOT_MODEL` | Zero-shot model | `phi3:latest` |
| `COPILOT_API_URL` | OpenAI-compatible proxy URL | `http://localhost:4141/v1` |
| `BIBOPS_NON_INTERACTIVE` | Disable interactive prompts in scripts | unset |
| `PYTHONPATH=.` | Required for direct `python -m ...` fallback commands | unset |

## Important Outputs

| Path | Description |
| --- | --- |
| `data/outputs/benchmark/comparison_results.json` | Architecture comparison output |
| `data/outputs/benchmark/charts/` | Generated benchmark charts |
| `data/runtime/` | JSONL traces and runtime logs |
| `data/databases/bibops.db` | SQLite server-status database |
| `data/databases/vectordb/` | Chroma vector database for RAG |
| `data/outputs/benchmark/security_race_report.json` | Racing Arena adversarial report |

