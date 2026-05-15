# Plan de lecture — Ayoub
> Périmètre : MCP Server · Protocole A2A · Adapters · Probes · Dev tools

---

## 1. Vue d'ensemble (15 min)

| Fichier | Ce qu'on y cherche |
|---|---|
| `AGENTS.md` | Protocoles A2A, interfaces agents, conventions inter-agents |
| `CLAUDE.md` | Sections "Adapters" + commandes CLI |
| `pyproject.toml` | Entry-point `bibops`, dépendances (typer, langgraph, fastapi, httpx…) |

---

## 2. MCP Server (45 min)

| Fichier | Points clés |
|---|---|
| `src/agent/mcp_server.py` | Exposition des 3 outils IT comme tools MCP — interface avec `lancer_agent()` |
| `src/bibops/benchmark/mcp_tools.py` | Client benchmark qui appelle les tools via le protocole MCP |
| `src/bibops/copilot/agent_mcp.py` | Agent Copilot qui utilise le MCP server comme backend |
| `src/bibops/copilot/smoke_test.py` | Test de fumée de la connexion Copilot |
| `src/bibops/research/mcp_demos/langchain_mcp.py` | Démo LangChain + MCP (code expérimental) |

---

## 3. Adapters et protocole A2A (1h)

Lire dans cet ordre — du plus générique au plus spécifique.

| Ordre | Fichier | Points clés |
|---|---|---|
| 1 | `src/bibops/adapters/base.py` | `BaseAgentAdapter` — interface abstraite : `run(ticket) -> str` |
| 2 | `src/bibops/adapters/registry.py` | `AdapterRegistry` — résolution dynamique par nom, enregistrement des adapters |
| 3 | `src/bibops/adapters/it_support.py` | Adapter IT Support — wraps `lancer_agent()` derrière l'interface `BaseAgentAdapter` |
| 4 | `src/bibops/adapters/openai_compat.py` | Adapter OpenAI-compatible API — n'importe quel modèle GPT/Claude via proxy |
| 5 | `src/bibops/adapters/a2a.py` | Protocole A2A — schémas Pydantic `A2ARequest`/`A2AResponse`, format JSON standardisé |
| 6 | `src/bibops/adapters/a2a_client.py` | Client HTTP A2A — Basic Auth (`A2A_USERNAME`/`A2A_PASSWORD`), appels POST |
| 7 | `src/bibops/benchmark/compare_a2a_agents.py` | Pipeline benchmark via A2A — compare plusieurs agents distants via le protocole |

---

## 4. Probes (20 min)

| Fichier | Points clés |
|---|---|
| `src/bibops/probes/schema.py` | `Probe` dataclass — champs : `id`, `category`, `question`, `expected_behavior` |
| `src/bibops/probes/loader.py` | `load_probes()`, `list_categories()` — lit les YAML de données/probes |

---

## 5. Dev tools (15 min)

| Fichier | Points clés |
|---|---|
| `src/bibops/dev/coverage_gates.py` | Seuils de couverture de tests — utilisé dans CI |

---

## 6. Tests unitaires (45 min)

| Fichier test | Ce qu'il couvre |
|---|---|
| `tests/conftest.py` | Fixtures pytest globales (tmp_path, monkeypatch…) |
| `tests/_fakes/fake_openai.py` | `FakeOpenAI(response_or_callable)`, `make_response(text)` — comprendre le pattern mock |
| `tests/unit/test_a2a_adapter.py` | `a2a.py` schémas Pydantic |
| `tests/unit/test_a2a_client.py` | Client HTTP A2A, Basic Auth |
| `tests/unit/test_adapter_registry.py` | Enregistrement/résolution adapters |
| `tests/unit/test_it_support_adapter.py` | Adapter IT Support |
| `tests/unit/test_openai_compat_adapter.py` | Adapter OpenAI-compatible |
| `tests/unit/test_probe_loader.py` | `load_probes()`, `list_categories()` |
| `tests/unit/test_model_config.py` | Configuration modèles |
| `tests/unit/test_copilot_api.py` | Connexion Copilot API |
| `tests/unit/test_runners_extras.py` | Runners complémentaires |

---

## Résumé — fichiers à maîtriser pour la soutenance

```
src/agent/mcp_server.py
src/bibops/adapters/   (6 fichiers clés : base, registry, it_support, openai_compat, a2a, a2a_client)
src/bibops/benchmark/compare_a2a_agents.py
src/bibops/benchmark/mcp_tools.py
src/bibops/probes/     (2 fichiers)
src/bibops/dev/coverage_gates.py
```

**Questions probables du jury sur ton périmètre :**
- Comment `AdapterRegistry` résout-il dynamiquement le bon adapter par nom ?
- Quelle est la différence entre l'adapter `it_support` et l'adapter `openai_compat` ?
- Comment le protocole A2A est-il structuré (`A2ARequest`/`A2AResponse`) et pourquoi Basic Auth ?
- Comment le MCP server expose-t-il les outils IT sans modifier `lancer_agent()` ?
- À quoi servent les `Probe` et comment `list_categories()` les organise-t-il ?
