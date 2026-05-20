# Plan de lecture — Ayoub
> Périmètre : Protocole A2A · Agents externes · Architecture globale (ReAct + LangGraph + Distributed)

---

## Fichiers à maîtriser (lire en détail)

### Protocole A2A & Agents externes (1h30)

Lire dans cet ordre — du contrat au client, puis au benchmark.

| Ordre | Fichier | Points clés |
|---|---|---|
| 1 | `src/bibops/adapters/base.py` | `BaseAgentAdapter` — interface abstraite : `run(ticket) -> str`, contrat minimal de tout agent |
| 2 | `src/bibops/adapters/registry.py` | `AdapterRegistry` — résolution dynamique par nom, enregistrement des adapters, pattern factory |
| 3 | `src/bibops/adapters/it_support.py` | Adapter IT Support — wraps `lancer_agent()` derrière `BaseAgentAdapter` |
| 4 | `src/bibops/adapters/openai_compat.py` | Adapter OpenAI-compatible — n'importe quel modèle GPT/Claude via proxy Copilot |
| 5 | `src/bibops/adapters/a2a.py` | [*] Protocole A2A — schémas Pydantic `A2ARequest`/`A2AResponse`, format JSON standardisé inter-agents |
| 6 | `src/bibops/adapters/a2a_client.py` | [*] Client HTTP A2A — Basic Auth (`A2A_USERNAME`/`A2A_PASSWORD`), appels POST, gestion erreurs HTTP |
| 7 | `src/bibops/benchmark/compare_a2a_agents.py` | [*] Pipeline benchmark A2A — compare plusieurs agents distants via le protocole, agrège les résultats |

**Questions jury** : Comment `AdapterRegistry` résout-il dynamiquement le bon adapter ? Quelle est la structure de `A2ARequest`/`A2AResponse` ? Pourquoi Basic Auth pour A2A ? Comment le benchmark A2A orchestre-t-il la comparaison d'agents distants ?

---

### Architecture — Agent IT Support ReAct (1h30)

Lire dans cet ordre — chaque couche s'appuie sur la précédente.

| Ordre | Fichier | Points clés |
|---|---|---|
| 1 | `src/agent/database.py` | Accès SQLite table `serveurs_it` — couche la plus basse |
| 2 | `src/agent/memory.py` | `MemoCourTerme` — liste de messages injectée dans le contexte LLM |
| 3 | `src/agent/tools.py` | Les 3 outils : `verifier_statut_serveur` (SQLite, 3s), `chercher_dans_kb` (JSON, 5s, 1 retry), `chercher_documentation_technique` (ChromaDB, 8s, 1 retry) — `ToolPolicy` frozen dataclass |
| 4 | `src/agent/rag.py` | Indexation ChromaDB, hybride BM25 + embedding, `RAG_DISTANCE_MAX=1.2`, collections `KB{id}` / `DOC_{name}` |
| 5 | `src/agent/maestro.py` | [*] **CŒUR** — `lancer_agent()`, `_call_llm()` → `AgentDecision` Pydantic, `KEYWORD_ROUTING` (hint), `TOOL_POLICIES`, boucle ReAct max 5 itérations, `MaestroRunTrace` JSONL |

**Questions jury** : Comment `KEYWORD_ROUTING` est-il un hint et non une contrainte ? Comment `ToolPolicy` gère-t-il timeouts et retries ? Qu'est-ce que `RAG_DISTANCE_MAX=1.2` ? Pourquoi JSON mode plutôt que regex ?

---

### Architecture — Racing Arena Distribuée (1h)

| Ordre | Fichier | Points clés |
|---|---|---|
| 1 | `src/racing/state.py` | `RacingState` (état LangGraph), `TelemetryData` (données SSE), `FinalDecision` (Literal `"PIT_STOP"` / `"STAY_OUT"`) |
| 2 | `src/racing/hub/server.py` | [*] FastAPI Hub — `GET /telemetry` (SSE), `POST /decision/{team_id}`, `GET /results`, `GET /race-history` ; `RaceEngine` lancé en tâche asyncio background |
| 3 | `src/racing/supervisor.py` | Logique superviseur LangGraph — routing conditionnel vers les experts |
| 4 | `src/racing/graph.py` | [*] Graphe LangGraph compilé — Supervisor → conditional routing → experts → Supervisor → END |
| 5 | `src/racing/team_client/main.py` | Process client — connexion SSE → désérialise `TelemetryData` → LangGraph → POST `/decision/{team_id}` |

**Questions jury** : Comment le protocole SSE fonctionne-t-il entre Hub et team clients ? Comment `FinalDecision` garantit-il `"PIT_STOP"` ou `"STAY_OUT"` uniquement ? Comment le graph LangGraph route-t-il vers les experts ? Pourquoi une architecture multi-processus plutôt que multi-thread ?

---

### Architecture — MCP Server (30 min)

| Fichier | Points clés |
|---|---|
| `src/agent/mcp_server.py` | [*] Exposition des 3 outils IT comme tools MCP — interface avec `lancer_agent()`, sans modifier la logique agent |
| `src/bibops/benchmark/mcp_tools.py` | Client benchmark qui appelle les tools via le protocole MCP |

**Questions jury** : Comment le MCP server expose-t-il les outils sans modifier `lancer_agent()` ? Quelle est la différence entre un appel direct à l'agent et un appel via MCP ?

---

## Fichiers à parcourir rapidement (skim)

| Fichier | Pourquoi le parcourir |
|---|---|
| `src/common/config.py` | `COPILOT_BASE_URL`, modèles par défaut, timeouts — constantes partagées |
| `src/common/llm_clients.py` | Singleton `get_copilot_client()`, `is_copilot_available()` TCP probe |
| `src/bibops/probes/schema.py` | `Probe` dataclass — id, category, question, expected_behavior |
| `src/bibops/probes/loader.py` | `load_probes()`, `list_categories()` — lecture des YAML |
| `src/racing/hub/race_engine.py` | 50 laps, 3s/lap — générateur de télémétrie (contexte pour SSE) |
| `src/racing/hub/rag_service.py` | RAG enrichissement décisions tactiques avec historique courses |
| `src/racing/experts.py` | Définitions des 3 experts partagés : tire, fuel, race engineer |
| `src/racing/team_client/nodes.py` | Nœuds LangGraph — chaque expert = `ChatOpenAI` call avec structured output |
| `src/racing/start_arena.py` | Lance les 3+ processus en parallèle (Hub + équipes) |
| `src/bibops/benchmark/core.py` | `run_benchmark()` — lit CSV, appelle LLM, écrit JSON |
| `src/bibops/copilot/agent_mcp.py` | Agent Copilot utilisant MCP comme backend |
---

## Résultats à connaître

| Fichier de données | Ce qu'il contient |
|---|---|
| `data/outputs/benchmark/a2a_agents_results.json` | Scores des agents A2A comparés |
| `data/outputs/benchmark/a2a_agents_report.md` | Rapport lisible de la comparaison A2A |
| `data/outputs/benchmark/benchmark_mcp.json` | Résultats du benchmark via MCP |

---

## Résumé — fichiers critiques

```
src/bibops/adapters/a2a.py              ← contrat protocole A2A
src/bibops/adapters/a2a_client.py       ← client HTTP A2A
src/bibops/benchmark/compare_a2a_agents.py  ← benchmark A2A
src/bibops/adapters/base.py             ← interface adapter
src/bibops/adapters/registry.py         ← résolution dynamique
src/bibops/adapters/it_support.py       ← adapter IT Support
src/bibops/adapters/openai_compat.py    ← adapter OpenAI proxy
src/agent/maestro.py                    ← architecture ReAct
src/agent/tools.py + rag.py             ← outils + RAG
src/agent/mcp_server.py                 ← exposition MCP
src/racing/hub/server.py                ← hub distribué FastAPI
src/racing/graph.py + supervisor.py     ← architecture LangGraph
src/racing/team_client/main.py          ← client SSE → LangGraph
```

---

## Questions probables du jury

- Quelle est la différence entre l'adapter `it_support` et l'adapter `openai_compat` ?
- Comment `AdapterRegistry` résout-il dynamiquement le bon adapter par nom ?
- Comment le protocole A2A est-il structuré (`A2ARequest`/`A2AResponse`) et pourquoi Basic Auth ?
- En quoi le protocole A2A permet-il d'évaluer des agents distants sans connaître leur implémentation ?
- Comment le MCP server expose-t-il les outils IT sans modifier `lancer_agent()` ?
- Comment fonctionne la boucle ReAct de `lancer_agent()` ? (max iterations, fallback, JSON mode)
- Comment le protocole SSE fonctionne-t-il entre Hub et team clients dans l'arène distribuée ?
- Comment le graph LangGraph route-t-il conditionnellement vers les experts depuis le Supervisor ?
- Pourquoi l'architecture multi-processus pour l'arène plutôt qu'asyncio dans un seul processus ?
- Comment `FinalDecision` garantit-il que la valeur est toujours `"PIT_STOP"` ou `"STAY_OUT"` ?
