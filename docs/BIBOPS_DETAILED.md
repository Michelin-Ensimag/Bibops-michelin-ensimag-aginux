# BibOps Detailed Overview

This document keeps the long-form explanation of BibOps, its architecture, and its main use cases. The root README is intentionally shorter and should remain the entry point for setup and the most common commands.

## Purpose

BibOps is a framework for evaluating LLM behavior in Michelin IT support scenarios. It was designed to answer a practical question: when should a support workflow use a direct LLM answer, and when does it need a tool-using multi-agent architecture?

The project compares two approaches:

- **LLM Unique**: a zero-shot model receives the ticket and answers without tools.
- **Systeme Multi-Agents**: a ReAct-style agent can inspect a knowledge base, query technical documentation through RAG, and check server status before producing a final answer.

The same framework also supports security probes, external A2A agent tests, MCP tool experiments, and the Racing Arena multi-agent simulation.

## Main Use Cases

### 1. IT Support Architecture Comparison

BibOps can run the same ticket set through both architectures and produce a structured comparison. This helps measure whether tool use improves response quality, root-cause analysis, and operational usefulness.

Typical command:

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

The output is written to `data/outputs/benchmark/comparison_results.json`.

### 2. Automated Evaluation

The evaluation engine scores answers across multiple dimensions:

- quality and usefulness
- security and policy compliance
- latency
- token/cost footprint
- greenops impact
- composite pass/fail verdict

The composite policy currently weights quality most heavily, while still gating on security and operational constraints.

### 3. Security and Red-Team Checks

BibOps includes rule-based security checks for common risks such as:

- prompt injection
- PII leakage
- secret exposure
- toxic content
- unsafe URLs
- weak refusal behavior

These checks are used by the evaluation registry and by benchmark validation flows.

### 4. MCP Tool Exposure

The IT support tools are exposed through an MCP server. This lets external agents call the same support capabilities used by the internal ReAct agent.

Start the MCP server:

```bash
bibops dev mcp-server
```

Direct module fallback:

```bash
PYTHONPATH=. python -m src.agent.mcp_server
```

### 5. External A2A Agent Benchmarking

BibOps can evaluate an external A2A-compatible agent over the same benchmark dataset. This is useful when comparing the internal implementation with a remote agent service.

Environment variables:

```bash
export A2A_USERNAME=...
export A2A_PASSWORD=...
```

Example command:

```bash
bibops bench a2a \
  --agents https://example.com/a2a \
  --max-probes 5 \
  --username "$A2A_USERNAME" \
  --password "$A2A_PASSWORD"
```

### 6. Racing Arena

The Racing Arena is a separate multi-agent experiment. A FastAPI hub streams race telemetry over SSE, and independent team clients make pit-stop decisions with LLM calls.

Modes:

```bash
bibops racing demo
bibops racing arena
bibops racing adversarial
```

The adversarial mode adds an attacker team and writes a security report to:

```text
data/outputs/benchmark/security_race_report.json
```

### 7. Reporting

BibOps can generate charts from benchmark output files:

```bash
bibops report charts
```

Charts are written under:

```text
data/outputs/benchmark/charts/
```

## System Architecture

```text
src/
  agent/
    maestro.py       ReAct loop and final support answer generation
    tools.py         Server status, JSON KB search, Chroma RAG
    mcp_server.py    MCP exposure for support tools
    rag.py           Vector search utilities

  bibops/
    cli/             Typer command tree
    benchmark/       Benchmark runners and validation
    evaluation/      Judges, metrics, policies, rule checks
    adapters/        Internal, A2A, and OpenAI-compatible adapters
    probes/          Probe loading and categorization
    reporting/       Chart generation
    dev/             Developer utilities

  common/
    config.py        Project constants and model defaults
    chat_models.py   Provider-aware chat abstraction
    llm_clients.py   Copilot/OpenAI-compatible client helpers
    text.py          Response parsing and error helpers

  racing/
    hub/             FastAPI hub, race engine, RAG service
    team_client/     Team process entry point
    graph.py         LangGraph decision graph
```

## IT Support Agent Flow

The core support agent lives in `src/agent/maestro.py` as `lancer_agent()`.

At a high level:

1. The user ticket is added to short-term memory.
2. Optional keyword routing suggests a likely tool before the first model call.
3. `_call_llm()` asks the configured provider/model for an `AgentDecision` Pydantic object.
4. If the decision names a tool, the agent executes it with the configured timeout and retry policy.
5. The tool result is inserted back into memory.
6. The loop continues until the model returns a final answer or the iteration limit is reached.

The agent returns:

```python
{
    "reponse_finale": "...",
    "trace": MaestroRunTrace(...)
}
```

Runtime traces are serialized as JSONL under:

```text
data/runtime/maestro/maestro_runs.jsonl
```

## Support Tools

The three production support tools are defined in `src/agent/tools.py`.

| Tool | Purpose | Data Source |
| --- | --- | --- |
| `verifier_statut_serveur(nom)` | Check the status of an IT server | SQLite `serveurs_it` table |
| `chercher_dans_kb(requete)` | Search the curated JSON knowledge base | Local JSON KB |
| `chercher_documentation_technique(requete)` | Retrieve technical documentation snippets | ChromaDB RAG |

Tool execution is controlled by the frozen `ToolPolicy` dataclass. Policies define timeouts and retry behavior per tool.

## LLM Providers

BibOps uses explicit provider/model pairs.

| Provider | Typical Use | Examples |
| --- | --- | --- |
| `ollama` | Local zero-shot and agent models | `phi3:latest`, `mistral:latest` |
| `copilot` | OpenAI-compatible remote models and judges | `gpt-4o`, `gpt-5.2` |

The Copilot/OpenAI-compatible proxy defaults to:

```text
http://localhost:4141/v1
```

Start it with:

```bash
npx copilot-api@latest start
```

Racing Arena team agents currently require GPT models through the proxy. Some non-GPT proxy models may return `400 model_not_supported` in that path.

## Evaluation Pipeline

Evaluation is coordinated by `EvaluatorRegistry`, which runs evaluators and merges their results.

Important components:

- `QualityEvaluator`: wraps `LLMProfessor` for IT-support-oriented grading.
- `LLMJudge`: generic scoring primitive returning `JudgeVerdict`.
- `LLMProfessor`: domain-specific wrapper that adds RCA context and can persist scores to an `evaluations` table when that schema is present.
- `SecurityLLMInspectorAdapter`: runs rule-based security checks.
- `CompositePolicy`: combines quality, security, finops, latency, and greenops into a score out of 100.
- `EvaluationEngine`: pure rule-based scoring for feedback, errors, speed, tokens, and F1 dimensions.

The composite policy uses these weights:

| Dimension | Weight |
| --- | ---: |
| Quality | 0.40 |
| Security | 0.35 |
| FinOps | 0.10 |
| Latency | 0.10 |
| GreenOps | 0.05 |

Current pass gates:

- quality score must be at least 7
- security score must be at least 6

## Command Reference

### Setup

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install -e .
bibops dev init-db
bibops dev build-vectordb
```

### Tests

```bash
bibops test unit
bibops test all
bibops test coverage
bibops dev coverage-gates
```

### Configuration

```bash
bibops config show
bibops config models
bibops config check --judge-model gpt-4o --agent-provider ollama --agent-model phi3:latest
```

### Benchmarks

```bash
bibops bench core mistral:latest
bibops bench compare-archs --max-tickets 10
bibops bench ab-test --mode llm
bibops bench position-bias --max-tickets 10
bibops bench a2a --agents https://example.com/a2a --max-probes 5
bibops bench mcp-tools
bibops bench validate --input data/outputs/benchmark/comparison_results.json
bibops bench kaggle --agent-provider ollama --agent-model mistral:latest --judge-model gpt-4o
```

### Evaluation

```bash
bibops eval pending --db data/databases/bibops.db
bibops eval process --input data/inputs/benchmark/tickets_evalues_fake.json
bibops eval suite security
```

### Development Utilities

```bash
bibops dev init-db
bibops dev build-vectordb
bibops dev mcp-server
bibops dev coverage-gates
```

### Copilot Tools

```bash
bibops copilot smoke-test
bibops copilot agent-mcp
```

### Reports

```bash
bibops report charts
```

### Racing Arena

```bash
bibops racing demo
bibops racing arena
bibops racing adversarial
```

Monitor a running arena:

```bash
tail -f logs/arena/team_team_psi.log
curl http://localhost:8000/race-history
curl http://localhost:8000/results
```

## Environment Variables

| Variable | Effect |
| --- | --- |
| `BIBOPS_NON_INTERACTIVE=1` | Skip interactive feedback prompts |
| `BIBOPS_JUDGE_MODEL` | Default Copilot/OpenAI-compatible judge model |
| `BIBOPS_AGENT_PROVIDER` | Default multi-agent provider: `ollama` or `copilot` |
| `BIBOPS_AGENT_MODEL` | Default multi-agent model |
| `BIBOPS_ZERO_SHOT_PROVIDER` | Default zero-shot provider: `ollama` or `copilot` |
| `BIBOPS_ZERO_SHOT_MODEL` | Default zero-shot model |
| `EVAL_BANK_AGENT_PROVIDER` | Optional provider override for integration evaluation suites |
| `BIBOPS_MAX_TICKETS` | Limit tickets processed in benchmarks |
| `BIBOPS_DEFAULT_FEEDBACK` | Default feedback choice in non-interactive mode |
| `BIBOPS_POSITION_MAX_TICKETS` | Default ticket count for position-bias tests |
| `COPILOT_API_URL` | Override Copilot proxy URL |
| `A2A_USERNAME` / `A2A_PASSWORD` | Basic Auth for A2A agent evaluation |
| `PYTHONPATH=.` | Required for direct module execution from repo root |

## Data Contracts

Important runtime contracts:

- `lancer_agent()` returns a dictionary with `reponse_finale` and `trace`.
- `MaestroRunTrace` is written as JSONL to `data/runtime/maestro/maestro_runs.jsonl`.
- Benchmark outputs are validated by the benchmark-output validator and include `schema_version`, `config`, `summary`, `quality`, `security`, `composite`, and `details`.
- RAG collections in ChromaDB are keyed as `KB{id}` and `DOC_{name}`.
- `bibops dev init-db` creates the `serveurs_it` table used by support-status lookup.
- `bibops eval pending` expects a database that already contains compatible `tickets` and `evaluations` tables.

## Testing Notes

Unit tests avoid network calls. Tests for the support agent patch `_call_llm` in `src/agent/maestro.py` and feed `AgentDecision` objects directly.

Useful test helpers:

- `tests/unit/test_maestro.py::make_fake_llm`
- `tests/_fakes/fake_openai.py::FakeOpenAI`
- `tests/_fakes/fake_openai.py::make_response`

Follow this pattern for new tests that need deterministic LLM behavior.

## Operational Notes

- Prefer the `bibops` CLI after `pip install -e .`.
- Use `PYTHONPATH=.` only for direct module fallback commands.
- Keep generated benchmark outputs under `data/outputs/`.
- Keep runtime traces under `data/runtime/`.
- Unit tests are safe without Ollama, the Copilot proxy, or external network access.
