# Plan de lecture — Widad
> Périmètre : Moteur d'évaluation · Juges LLM · Scoring composite · Benchmark comparatif · A/B Testing · Biais de position

---

## 1. Vue d'ensemble (15 min)

| Fichier | Ce qu'on y cherche |
|---|---|
| `README.md` | Sections Evaluation + Benchmark uniquement |
| `CLAUDE.md` | Sections "Evaluation engine" + "Key data contracts" |

---

## 2. Contrats de données (30 min)

| Fichier | Points clés |
|---|---|
| `src/bibops/evaluation/result_schema.py` | `EvaluationResult` — clés JSON de sortie benchmark |
| `src/bibops/evaluation/config.py` | Constantes d'évaluation (gates, seuils par défaut) |
| `src/bibops/evaluation/scoring/thresholds.py` | `ScoreThreshold`, `ScoreVerdict`, `load_thresholds()`, `evaluate_score()` |

---

## 3. Juges LLM `src/bibops/evaluation/judges/` (1h)

Lire dans cet ordre — `LLMProfessor` wraps `LLMJudge`.

| Ordre | Fichier | Points clés |
|---|---|---|
| 1 | `src/bibops/evaluation/judges/llm_judge.py` | `LLMJudge`, `JudgeVerdict(score: float, justification: str)`, `score(criterion, question, answer)` — primitive générique |
| 2 | `src/bibops/evaluation/judges/llm_professor.py` | `LLMProfessor` — wraps `LLMJudge` + contexte RCA, persistance SQLite, batch `evaluer_tickets_en_attente()` |
| 3 | `src/bibops/evaluation/judges/rule_engine.py` | `EvaluationEngine` — scoring purement déterministe : error/feedback/speed/token/F1 (sans LLM) |
| 4 | `src/bibops/evaluation/rca.py` | Root Cause Analysis — enrichit le contexte du juge |
| 5 | `src/bibops/evaluation/quality_evaluator.py` | `QualityEvaluator` — adapte `LLMProfessor` vers l'interface `EvaluatorRegistry` |

---

## 4. Métriques et scoring composite (1h)

| Fichier | Points clés |
|---|---|
| `src/bibops/evaluation/metrics/composite.py` | ⭐ `CompositePolicy.evaluate()` — formule : quality×0.40 + security×0.35 + finops×0.10 + latency×0.10 + greenops×0.05 → score/100 ; gates PASS/FAIL (quality≥7, security≥6) ; `_inverse_minmax` pour latence |
| `src/bibops/evaluation/metrics/consistency.py` | Cohérence multi-réponses (détecte les contradictions) |
| `src/bibops/evaluation/reporting/regression.py` | Détection de régression entre deux runs benchmark |

---

## 5. Registre d'évaluateurs (30 min)

| Fichier | Points clés |
|---|---|
| `src/bibops/evaluation/registry.py` | `EvaluatorRegistry` — enregistre `QualityEvaluator` + `SecurityLLMInspectorAdapter`, lance les deux en parallèle, merge les résultats |

---

## 6. Benchmark core + Compare architectures (1h30)

| Fichier | Points clés |
|---|---|
| `src/bibops/benchmark/core.py` | `run_benchmark()` — lit le CSV, appelle `ollama.chat`, `extraire_texte_reponse()`, `extraire_compteurs_tokens()`, demande feedback utilisateur, écrit JSON |
| `src/bibops/benchmark/compare_architectures.py` | ⭐ Pipeline LLM Unique vs Multi-Agents — `ComparaisonResult`, calcul `domain_summary`, latence totale, tokens, coût USD, empreinte CO2e, verdict release |
| `src/bibops/benchmark/validate_benchmark_output.py` | Validation schéma JSON de sortie (clés : `schema_version`, `config`, `summary`, `quality`, `security`, `composite`, `details`) |

---

## 7. A/B Testing (45 min)

| Fichier | Points clés |
|---|---|
| `src/bibops/benchmark/ab_test_llm.py` | Jugement LLM automatique entre deux réponses — `appeler_modele()`, `_extraire_json_depuis_texte()`, `_normaliser_choix()`, helpers erreur (`_est_reponse_erreur`, `_est_quota_free_epuise`, etc.), `_executer_avec_timeout()` |
| `src/bibops/benchmark/ab_test_llm_statements.py` | Prompts/statements pour le juge A/B |
| `src/bibops/benchmark/ab_test_user.py` | Version interactive — l'utilisateur choisit A ou B manuellement |

---

## 8. Biais de position (30 min)

| Fichier | Points clés |
|---|---|
| `src/bibops/benchmark/position_bias.py` | Test de biais de position — inverse l'ordre A/B et compare les verdicts pour détecter si le juge favorise systématiquement la première réponse |
| `src/bibops/benchmark/position_bias_statements.py` | Prompts statiques pour le test de biais |

---

## 9. Tests unitaires (1h)

| Fichier test | Ce qu'il couvre |
|---|---|
| `tests/unit/test_llm_judge.py` | `LLMJudge.score()` avec `FakeOpenAI` |
| `tests/unit/test_llm_professor_judge.py` | `LLMProfessor`, persistance SQLite |
| `tests/unit/test_quality_evaluator.py` | `QualityEvaluator` via registry |
| `tests/unit/test_composite_policy.py` | Formule de pondération, gates PASS/FAIL |
| `tests/unit/test_evaluator_registry.py` | Merge des résultats multi-évaluateurs |
| `tests/unit/test_rule_engine_v2.py` | `EvaluationEngine` déterministe |
| `tests/unit/test_regression.py` | Détection de régression |
| `tests/unit/test_thresholds.py` | `evaluate_score()` avec seuils |
| `tests/unit/test_result_schema.py` | Validation schéma JSON |
| `tests/unit/test_benchmark_core.py` | `run_benchmark()`, helpers extraction, feedback |
| `tests/unit/test_ab_test_llm.py` | Pipeline A/B complet avec mock LLM |

---

## 10. Tests d'intégration qualité + robustesse (20 min)

| Fichier test | Ce qu'il couvre |
|---|---|
| `tests/integration/quality/test_relevance.py` | Pertinence des réponses |
| `tests/integration/quality/test_use_case.py` | Cas d'usage IT support |
| `tests/integration/robustness/test_consistency.py` | Cohérence multi-réponses |

---

## Ressources annexes

| Fichier | Utilité |
|---|---|
| `tests/_fakes/fake_openai.py` | `FakeOpenAI`, `make_response()` — comprendre comment mocker le client OpenAI dans les tests |
| `tests/conftest.py` | Fixtures pytest globales |

---

## Résumé — fichiers à maîtriser pour la soutenance

```
src/bibops/evaluation/judges/          (5 fichiers)
src/bibops/evaluation/metrics/composite.py
src/bibops/evaluation/registry.py
src/bibops/evaluation/scoring/thresholds.py
src/bibops/benchmark/core.py
src/bibops/benchmark/compare_architectures.py
src/bibops/benchmark/ab_test_llm.py
src/bibops/benchmark/position_bias.py
```

**Questions probables du jury sur ton périmètre :**
- Quelle est la différence de rôle entre `LLMJudge` et `LLMProfessor` ?
- Comment `CompositePolicy` calcule-t-il le score final et quels sont les gates PASS/FAIL ?
- Comment le test de biais de position fonctionne-t-il et qu'a-t-on détecté ?
- Pourquoi quality×0.40 et security×0.35 — justification de ces pondérations ?
- Comment `EvaluatorRegistry` orchestre-t-il les deux évaluateurs en parallèle ?
