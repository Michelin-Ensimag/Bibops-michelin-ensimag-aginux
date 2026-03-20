# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BibOps is a fully local (sovereign) IT support agent for Michelin. It uses Ollama for local LLMs, SQLite for operational data, ChromaDB for vector search, and a JSON knowledge base for keyword-based retrieval. No cloud APIs are required for the core agent.

## Commands

### Setup (one-time)
```bash
pip install -r requirements.txt
pip install chromadb langchain langchain-ollama langchain-community langchain-core pydantic mcp fastmcp langsmith langchain-deeplake
python src/agents/baseSQL.py        # Initialize SQLite DB and seed test data
python src/agents/memoire_RAG.py    # Vectorize KB articles into ChromaDB
ollama pull phi3:latest             # Pull default agent LLM
ollama pull mistral:latest          # Pull judge LLM (used by LLMProfessor)
```

### Running the agent
```bash
python src/agents/maestro.py        # Runs 2 test scenarios
python src/agents/serveur_mcp.py    # Start MCP server (for Claude Desktop/Cursor)
```

### Benchmarking
```bash
python src/benchmark/benchmark_pipeline.py   # Full agent pipeline (SQLite tickets → SQLite results)
python src/benchmark/benchmark.py            # Raw Ollama call, no agent layer (CSV + human feedback)
python src/benchmark/benchmark_langsmith.py  # Agent + LLM judge + LangSmith tracing
python src/benchmark/benchmark_mcp_tools.py  # MCP tools benchmark via MCP protocol (async)
python src/llm_professor/evaluation.py       # Rule-based scoring from tickets_evalues_fake.json
```

### Copilot API agent (requires GitHub Copilot proxy)
```bash
# Terminal 1:
npx copilot-api@latest start        # Start proxy on localhost:4141
# Terminal 2:
python3 -m src.llm_professor.agent_copilot_mcp   # Multi-model benchmark (gpt-4o, claude-haiku)
python scripts/test_copilot_api.py               # Quick Copilot API smoke test (no MCP)
```

### LangChain chatbot (experimental, in docs/)
```bash
python docs/lang-chatbot/main.py    # RAG pipeline demo using DeepLake + HuggingFace embeddings
```

### Tests
```bash
pytest tests/
pytest tests/test_outils.py        # Unit tests for outils.py (fully mocked, no external deps)
pytest tests/test_memoire.py       # Unit tests for MemoCourTerme (no external deps)
pytest tests/test_maestro.py       # Integration tests (require Ollama running)
```

## Architecture

### Data Layer (three sources)
- **SQLite** (`data/databases/bibops.db`): `serveurs_it` (server status), `tickets` (user requests), `evaluations` (benchmark results). Seeded by `baseSQL.py`.
- **ChromaDB** (`data/databases/vectordb/`): Semantic vector search over KB articles. Collection name: `"doc_michelin"`. Rebuilt on each `memoire_RAG.py` run. Distance threshold: 1.2 (cosine) to reject irrelevant results.
- **JSON KB** (`data/knowledge_base/knowledge_base.json`): Keyword-scored retrieval with `mots_cles`, `probleme`, `solution` fields. Top-3 results returned by score.

Both databases are auto-generated and excluded from git.

### Agent Loop (`src/agents/`)
- **maestro.py**: ReAct loop (max 5 iterations). `lancer_agent(contexte, ticket_utilisateur, outils_disponibles, modele)` — note context is the first argument. Parses `ACTION: nom_outil("argument")` from LLM output via regex (falls back to single quotes). Deduplicates tool calls by `(tool_name, lowered_arg)` key. System prompt is dynamically generated from tool docstrings.
- **memoire_courte.py**: Sliding window conversation history (`MemoCourTerme`, default max 50 messages).
- **outils.py**: Three tools exposed to the agent: `verifier_statut_serveur` (SQLite, with exact then partial word matching), `chercher_dans_kb` (JSON keyword scoring), `chercher_documentation_technique` (ChromaDB). Uses a module-level singleton for the ChromaDB client to avoid reconnections. Native stderr is silenced during ChromaDB init to suppress grpc/absl noise.
- **serveur_mcp.py**: FastMCP wrapper exposing the same three tools over stdio for external MCP clients (Claude Desktop, Cursor). Run as a standalone process.
- **rca_engine.py** (in `src/llm_professor/`): Optional pre-processing step (currently commented out in maestro.py). Uses Ollama to identify the failing service (VPN/CISCO/Outlook) before the ReAct loop.

### Evaluation Pipeline (`src/llm_professor/`)

There are **two independent evaluation systems**:

1. **LLM-based judge** (`evaluation_manager.py`): `LLMProfessor` uses Mistral as a judge LLM (via LangChain + Ollama) to score agent responses **1–5** on Relevance, Clarity, Completeness. Uses Pydantic `EvaluationResult(note, justification)` with `temperature=0.0` and `format="json"`. Saves results to the `evaluations` SQLite table.
   - `eva_mg_lang.py`: Corrected version of `evaluation_manager.py` (fixed indentation of `evaluer_reponse`, but `_sauvegarder_en_base` is accidentally defined as a module-level function instead of a class method — it will fail at runtime).
   - `eva_mg_rev_proxy.py`: Variant that replaces Mistral with a local OpenAI-compatible proxy at `http://localhost:4141/v1` (e.g., GitHub Copilot via proxy), using `ChatOpenAI` instead of `ChatOllama`.

2. **Rule-based scoring** (`evaluer_responses.py` + `config_evaluation.py`): `EvaluationEngine` scores **0–10** based on weighted criteria: error presence (25%), user feedback (35%), response time (20%), token efficiency (20%). Weights and thresholds are configured in `config_evaluation.py`. `EvaluationProcessor` reads `data/benchmark/tickets_evalues_fake.json` and writes `data/benchmark/tickets_evalues_scores.json`.

- **agent_copilot_mcp.py**: Bridges the Copilot API proxy (`localhost:4141`) with the MCP server. Translates MCP tools to OpenAI function-calling format, sends tickets to multiple models (gpt-4o-mini, gpt-4o, claude-haiku-4.5), executes tool calls via MCP, and scores results with `EvaluationEngine`. Saves to `data/benchmark/benchmark_copilot_mcp.json`. Requires `npx copilot-api@latest start` in a separate terminal.

### Evaluation Module (`src/llm_professor/evaluation.py`)

Single unified module for both evaluation systems:

1. **`LLMProfessor`** (LLM judge via Copilot proxy): scores responses 0–10 with justification, persists to SQLite. Includes `evaluer_tickets_en_attente()` for batch evaluation with RCA enrichment. Requires proxy on `localhost:4141`.
2. **`EvaluationEngine`** (rule-based, no LLM): weighted score 0–10 across error presence (25%), user feedback (35%), response time (20%), token efficiency (20%). Used by `benchmark_mcp_tools.py` and `agent_copilot_mcp.py`.
3. **`EvaluationProcessor`**: reads `tickets_evalues_fake.json`, writes `tickets_evalues_scores.json`. Run directly: `python src/llm_professor/evaluation.py` (rule-based) or `python src/llm_professor/evaluation.py --llm-judge` (proxy test).

### LangChain Chatbot (`docs/lang-chatbot/`)
- **main.py**: Standalone RAG demo (not integrated with the main agent). Loads web articles, splits into chunks, embeds with HuggingFace `all-MiniLM-L6-v2`, stores in a local DeepLake vector store (`chatbot_article_dataset/`), and answers queries using Ollama phi3 with `ConversationBufferMemory`.
- **lang-agent.py**: Incomplete prototype sketch for a LangChain-native agent with a `ModelFallbackMiddleware`. Not runnable as-is.

## Key Paths

| Path | Purpose |
|------|---------|
| `data/knowledge_base/articles/KB*/article.md` | Official Michelin KB articles (ingested by memoire_RAG) |
| `data/knowledge_base/knowledge_base.json` | Structured KB for keyword search |
| `data/benchmark/tickets_scenario_1.csv` | Test tickets for benchmark.py |
| `data/benchmark/tickets_evalues_fake.json` | Fake ticket responses for rule-based scoring |
| `data/databases/bibops.db` | Auto-generated SQLite (gitignored) |
| `data/databases/vectordb/` | Auto-generated ChromaDB (gitignored) |

## Test Infrastructure

- **`conftest.py`** (project root): Adds the project root to `sys.path` so `from src.agents.*` imports work regardless of launch directory. Also injects a `langchain.verbose` / `langchain.debug` shim for compatibility between `langchain-core 0.2.x` and `langchain >= 1.0`.
- **`tests/test_1.py`**: Hits the real SQLite database — requires `baseSQL.py` to have been run first.
- **`tests/test_outils.py`**: Fully mocked (SQLite, JSON KB, ChromaDB) — no external dependencies.
- **`tests/test_memoire.py`**: No external dependencies.

## Known Issues

- **`tests/test_maestro.py`**: The call to `lancer_agent` has swapped arguments — it passes the ticket text as `contexte` and the context string as `ticket_utilisateur`, opposite of `maestro.py`'s signature.

## Environment Variables (LangSmith)

`benchmark_langsmith.py` requires LangSmith credentials. Set these before running:
```bash
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY=<your_key>
export LANGCHAIN_PROJECT=BibOps-Local-Eval
```
