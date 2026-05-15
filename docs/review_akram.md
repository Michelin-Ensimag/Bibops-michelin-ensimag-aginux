# Plan de lecture — Akram
> Périmètre : Fondations communes · Agent ReAct · RAG/ChromaDB · Sécurité · Recherche expérimentale · CLI Typer · Kaggle · Racing Arena (Hub + LangGraph teams)

---

## 1. Vue d'ensemble du projet (30 min)

| Fichier | Ce qu'on y cherche |
|---|---|
| `README.md` | Pitch, prérequis, commandes de démarrage |
| `CLAUDE.md` | Architecture modules, conventions, data contracts |
| `pyproject.toml` | Dépendances (ollama, chromadb, pydantic…), entry-point `bibops` |

---

## 2. Utilitaires partagés `src/common/` (45 min)

| Fichier | Points clés |
|---|---|
| `src/common/config.py` | `COPILOT_BASE_URL`, `DEFAULT_*_MODEL`, `OLLAMA_OPTIONS`, `INPUT_CSV`, `OUTPUT_DIR` |
| `src/common/text.py` | `charger_copilot_api_key()`, `extraire_texte_reponse()`, `extraire_compteurs_tokens()`, `_get_attr()`, `contains_timeout()` |
| `src/common/llm_clients.py` | Singleton `get_copilot_client()`, `is_copilot_available()` (TCP probe) |
| `src/common/math_utils.py` | `clamp(value, low, high)` |
| `src/common/chat_models.py` | Wrapper modèles chat |

---

## 3. Agent IT Support `src/agent/` (1h30)

Lire dans cet ordre strict — chaque fichier dépend du précédent.

| Ordre | Fichier | Points clés |
|---|---|---|
| 1 | `src/agent/database.py` | Accès SQLite table `serveurs_it` |
| 2 | `src/agent/memory.py` | `MemoCourTerme` — liste de messages injectée dans le contexte LLM |
| 3 | `src/agent/tools.py` | Les 3 outils : `verifier_statut_serveur` (SQLite, 3s), `chercher_dans_kb` (JSON, 5s, 1 retry), `chercher_documentation_technique` (ChromaDB, 8s, 1 retry) · `ToolPolicy` frozen dataclass |
| 4 | `src/agent/rag.py` | Indexation ChromaDB, hybride BM25 + embedding, `RAG_DISTANCE_MAX=1.2`, collections `KB{id}` / `DOC_{name}` |
| 5 | `src/agent/maestro.py` | ⭐ CŒUR — `lancer_agent()`, `_call_llm()` → `AgentDecision` Pydantic (tool/argument/final_answer), `KEYWORD_ROUTING`, `TOOL_POLICIES`, `MaestroRunTrace` JSONL, max 5 itérations, fallback synthèse déterministe |

---

## 4. Sécurité `src/bibops/evaluation/` (1h)

| Fichier | Points clés |
|---|---|
| `src/bibops/evaluation/security_profile.py` | `SecurityProfile` dataclass — markers, seuils, `enabled_checks`, `block_threshold` |
| `src/bibops/evaluation/checks.py` | Détecteurs purs : PII regex, secrets (Bearer/api_key), injection markers, refusal phrases, `extract_urls()`, toxicity heuristic |
| `src/bibops/evaluation/security_evaluator.py` | `SecurityLLMInspectorAdapter` — `_RiskPack` (6 dimensions), scoring 0–10, `findings` format `dimension:detail` |
| `src/bibops/evaluation/metrics/greenops.py` | Calcul empreinte gCO2e, coût USD par token |

---

## 5. Recherche expérimentale `src/bibops/research/` (30 min)

| Fichier | Points clés |
|---|---|
| `src/bibops/research/adversarial.py` | Payloads adversariaux (prompt injection templates) |
| `src/bibops/research/discriminator.py` | Modèle discriminateur GAN — distingue réponses LLM Unique vs Multi-Agents |

---

## 6. Reporting (15 min)

| Fichier | Points clés |
|---|---|
| `src/bibops/reporting/charts.py` | Génération PNG matplotlib (bar charts, radar sécurité) |

---

## 7. CLI Typer `src/bibops/cli/` (1h)

| Fichier | Points clés |
|---|---|
| `src/bibops/cli/main.py` | Entry-point Typer, `app` principal, enregistrement des sous-apps |
| `src/bibops/cli/_shell.py` | Helpers shell communs (rich console, confirmation prompts) |
| `src/bibops/cli/commands/bench.py` | `bibops bench compare-archs`, `ab-test`, `position-bias`, `validate`, `kaggle` |
| `src/bibops/cli/commands/eval.py` | `bibops eval pending`, `bibops eval process` |
| `src/bibops/cli/commands/dev.py` | `bibops dev init-db`, `build-vectordb`, `mcp-server` |
| `src/bibops/cli/commands/racing.py` | `bibops racing demo`, `arena`, `adversarial` |
| `src/bibops/cli/commands/report.py` | Génération rapports |
| `src/bibops/cli/commands/config.py` | Affichage configuration |
| `src/bibops/cli/commands/copilot.py` | Commandes Copilot |
| `src/bibops/cli/commands/test.py` | Commandes test lancées depuis CLI |

---

## 8. Kaggle (20 min)

| Fichier | Points clés |
|---|---|
| `src/bibops/benchmark/local_kaggle_exam.py` | Évaluation benchmark Kaggle IT support — compare les réponses du modèle contre un ground truth |

---

## 9. Racing Arena — État partagé (30 min)

| Fichier | Points clés |
|---|---|
| `src/racing/state.py` | `RacingState` (LangGraph state), `TelemetryData` (données SSE), `FinalDecision` (Literal `"PIT_STOP"` / `"STAY_OUT"`) |
| `src/racing/shared/attack_payloads.py` | Payloads d'attaque adversariale injectés par l'équipe Ψ |
| `src/racing/shared/security_metrics.py` | Métriques de sécurité spécifiques au racing — détection d'attaques |

---

## 10. Racing Arena — Hub FastAPI (1h)

| Ordre | Fichier | Points clés |
|---|---|---|
| 1 | `src/racing/hub/race_engine.py` | `RaceEngine` — 50 laps, 3s/lap, état de course, génération télémétrie, push vers queues SSE |
| 2 | `src/racing/hub/server.py` | ⭐ FastAPI app — `GET /telemetry` (SSE), `POST /decision/{team_id}`, `GET /results`, `GET /race-history` ; `RaceEngine` lancé comme tâche asyncio background |
| 3 | `src/racing/hub/observer.py` | `RaceObserver` — consomme la télémétrie pour logging et métriques |
| 4 | `src/racing/hub/rag_service.py` | RAG service pour enrichir les décisions tactiques avec historique de courses |
| 5 | `src/racing/hub/ingest.py` | Ingestion des données historiques course dans ChromaDB |

---

## 11. Racing Arena — Client LangGraph (1h)

| Ordre | Fichier | Points clés |
|---|---|---|
| 1 | `src/racing/experts.py` | Définitions des 3 experts partagés : tire engineer, fuel engineer, race engineer |
| 2 | `src/racing/supervisor.py` | Logique superviseur LangGraph — routing conditionnel vers les experts |
| 3 | `src/racing/graph.py` | Graphe LangGraph principal compilé (Supervisor → conditional routing → experts → Supervisor → END) |
| 4 | `src/racing/team_client/state_tools.py` | Outils de manipulation du state LangGraph |
| 5 | `src/racing/team_client/nodes.py` | Nœuds LangGraph — chaque expert est un `ChatOpenAI` call avec structured output |
| 6 | `src/racing/team_client/graph.py` | Graphe team_client compilé |
| 7 | `src/racing/team_client/main.py` | ⭐ Process client — connexion SSE → `TelemetryData` → LangGraph → `POST /decision/{team_id}` |

---

## 12. Racing Arena — Équipes spécialisées (45 min)

| Fichier | Points clés |
|---|---|
| `src/racing/team_validated/nodes.py` + `graph.py` + `state_tools.py` + `main.py` | Équipe C — decisions validées par second LLM call avant envoi |
| `src/racing/team_psi/main.py` | ⭐ Équipe Ψ — attaquante adversariale : injecte des payloads dans les décisions |
| `src/racing/team_zero_shot/main.py` | Équipe A — baseline zero-shot sans LangGraph |
| `src/racing/demo.py` | Démo standalone (pas de hub) — boucle locale |
| `src/racing/start_arena.py` | Lance les 3+ processus en parallèle (Hub + équipes) |

---

## 13. Tests unitaires (1h30)

| Fichier test | Ce qu'il couvre |
|---|---|
| `tests/unit/test_maestro.py` | `make_fake_llm()`, scénarios ReAct complets, fallback |
| `tests/unit/test_outils.py` | 3 outils avec mocks SQLite/JSON/ChromaDB |
| `tests/unit/test_memoire.py` | `MemoCourTerme` |
| `tests/unit/test_security_evaluator.py` | `_RiskPack`, heuristiques, `SecurityLLMInspectorAdapter` |
| `tests/unit/test_checks.py` | Détecteurs PII/injection/secrets/URL |
| `tests/unit/test_greenops.py` | Métriques CO2e/coût |
| `tests/unit/test_common_text.py` | Helpers text/tokens (namespace `T` = text, `AB` = ab_test_llm) |
| `tests/unit/test_common_llm_clients.py` | Singleton client, TCP probe |
| `tests/unit/test_report_charts.py` | Charts matplotlib |
| `tests/unit/test_agent_infra.py` | Infra agent — **note : peut échouer sans ChromaDB env** |
| `tests/unit/test_racing_engine.py` | `RaceEngine` — générations télémétrie, logique laps |
| `tests/unit/test_racing_nodes.py` | Nœuds LangGraph (tire/fuel/race engineers) |
| `tests/unit/test_racing_observer.py` | `RaceObserver` |
| `tests/unit/test_racing_extras.py` | Scénarios racing additionnels |
| `tests/unit/test_runners_extras.py` | Runners complémentaires |
| `tests/unit/test_racing_server.py` | FastAPI routes — **note : env ChromaDB requis** |
| `tests/unit/test_racing_daemon_helpers.py` | Helpers daemon — **note : env requis** |

---

## 14. Tests d'intégration sécurité + outils (30 min)

| Fichier test | Ce qu'il couvre |
|---|---|
| `tests/integration/security/test_pii_detection.py` | Détection PII dans les réponses |
| `tests/integration/security/test_prompt_injection.py` | Résistance à l'injection |
| `tests/integration/security/test_secret_leakage.py` | Fuite de secrets |
| `tests/integration/security/test_harmful_content.py` | Toxicité/contenu nuisible |
| `tests/integration/tool_use/test_tool_detection.py` | Sélection correcte du bon outil |

---

## Résumé — fichiers à maîtriser pour la soutenance

```
src/common/                    (5 fichiers)
src/agent/                     (5 fichiers clés : database, memory, tools, rag, maestro)
src/bibops/evaluation/security_*.py  (2 fichiers)
src/bibops/evaluation/checks.py
src/bibops/evaluation/metrics/greenops.py
src/bibops/research/adversarial.py + discriminator.py
src/bibops/reporting/charts.py
src/bibops/cli/                (main.py + 8 commands)
src/bibops/benchmark/local_kaggle_exam.py
src/racing/hub/server.py       ← point d'entrée FastAPI
src/racing/hub/race_engine.py  ← logique de course
src/racing/team_client/main.py ← client SSE → LangGraph
src/racing/team_psi/main.py    ← vecteur adversarial
src/racing/start_arena.py      ← orchestration multi-process
```

**Questions probables du jury sur ton périmètre :**
- Comment fonctionne la boucle ReAct de `lancer_agent()` ? (max iterations, fallback, JSON mode)
- Pourquoi `KEYWORD_ROUTING` est un hint et non une contrainte ?
- Comment `ToolPolicy` gère-t-il les timeouts et retries ?
- Qu'est-ce que `RAG_DISTANCE_MAX=1.2` et pourquoi cette valeur ?
- Comment `SecurityLLMInspectorAdapter` calcule-t-il son score 0–10 depuis `_RiskPack` ?
- Comment fonctionne le protocole SSE entre le Hub et les team clients ?
- Comment `FinalDecision` garantit-il que la valeur est toujours `"PIT_STOP"` ou `"STAY_OUT"` ?
- Quel est le vecteur d'attaque de l'équipe Ψ et comment les autres équipes s'en protègent-elles ?
- Comment le graph LangGraph route-t-il vers les experts (Supervisor → conditional → END) ?
- Comment `bibops racing adversarial` diffère-t-il de `bibops racing arena` ?
