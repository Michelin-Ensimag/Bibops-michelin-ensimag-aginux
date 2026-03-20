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
python src/benchmark/benchmark_mcp.py        # Full pipeline (agent + tools + DB)
python src/benchmark/benchmark.py            # Raw Ollama call, no agent layer
python src/benchmark/benchmark_langsmith.py  # With LangSmith tracing + LLM judge
python src/llm_professor/client_mcp.py       # MCP tool benchmark via MCP protocol (async)
python src/llm_professor/evaluer_responses.py  # Rule-based scoring from tickets_evalues_fake.json
```

### LangChain chatbot (experimental)
```bash
python src/lang-chatbot/main.py     # RAG pipeline demo using DeepLake + HuggingFace embeddings
```

### Tests
```bash
pytest tests/
pytest tests/test_1.py             # Unit tests for outils.py (require seeded SQLite, no Ollama)
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

- **client_mcp.py**: Async MCP client that spawns `serveur_mcp.py` as a subprocess, calls each tool over the MCP protocol with test tickets, and scores results with `EvaluationEngine`. Saves to `data/benchmark/benchmark_mcp.json`.

### LangChain Chatbot (`src/lang-chatbot/`)
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

## Known Issues

- **`benchmark_langsmith.py` line 9**: The LangSmith API key is hardcoded in the source file. Remove it and use the environment variable `LANGCHAIN_API_KEY` instead before committing.
- **`evaluation_manager.py`**: The `evaluer_reponse` method is missing its `try:` block (indentation error). The code under the method body starting at line 46 should be wrapped in `try/except`. See `eva_mg_rev_proxy.py` for the correct pattern.
- **`eva_mg_lang.py`**: `_sauvegarder_en_base` is defined at module level instead of as a class method — it will raise a `TypeError` at runtime when called.
- **`tests/test_maestro.py`**: The call to `lancer_agent` has swapped arguments — it passes the ticket text as `contexte` and the context string as `ticket_utilisateur`, opposite of `maestro.py`'s signature.

## Environment Variables (LangSmith)

`benchmark_langsmith.py` requires LangSmith credentials. Set these before running:
```bash
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY=<your_key>
export LANGCHAIN_PROJECT=BibOps-Local-Eval
```
