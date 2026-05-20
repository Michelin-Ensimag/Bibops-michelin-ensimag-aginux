# Plan de lecture — Widad
> Périmètre : Introduction du projet · A/B Testing · Résultats & Comparaison d'architectures

---

## Fichiers à maîtriser (lire en détail)

### Introduction & Vue d'ensemble (30 min)

| Fichier | Ce qu'on y cherche |
|---|---|
| `README.md` | [*] **Pitch complet** du projet — contexte Michelin, problème résolu, deux architectures (LLM Unique vs Multi-Agents), commandes de démarrage — **tu dois présenter ce pitch au jury** |
| `CLAUDE.md` | Sections "Evaluation engine" et "Key data contracts" — comprendre la chaîne d'évaluation |
| `docs/BIBOPS_DETAILED.md` | Documentation détaillée du projet si disponible — contexte métier Michelin |

**Questions jury** : Quel est le problème que BibOps résout pour Michelin IT Support ? Pourquoi deux architectures à comparer ? Quels sont les critères de comparaison ?

---

### A/B Testing LLM (1h30)

Lire dans cet ordre.

| Ordre | Fichier | Points clés |
|---|---|---|
| 1 | `src/bibops/benchmark/ab_test_llm_statements.py` | Prompts statiques pour le juge A/B — comment la question est formulée au LLM juge |
| 2 | `src/bibops/benchmark/ab_test_llm.py` | [*] Pipeline A/B automatique — `appeler_modele()`, `_extraire_json_depuis_texte()`, `_normaliser_choix()`, helpers erreur (`_est_reponse_erreur`, `_est_quota_free_epuise`), `_executer_avec_timeout()`, logique de jugement |
| 3 | `src/bibops/benchmark/ab_test_user.py` | Version interactive — l'utilisateur humain choisit A ou B manuellement |
| 4 | `src/bibops/benchmark/position_bias.py` | [*] Test de biais de position — inverse l'ordre A/B et compare les verdicts pour détecter si le juge favorise systématiquement la première réponse |
| 5 | `src/bibops/benchmark/position_bias_statements.py` | Prompts statiques pour le test de biais de position |

**Questions jury** : Comment le juge LLM tranche-t-il entre la réponse A et B ? Qu'est-ce que le biais de position et comment est-il détecté ? Quelle différence entre A/B LLM et A/B utilisateur ? Que faire si le juge répond une chaîne non-parsable ?

---

### Résultats — Comparaison d'architectures (1h)

| Ordre | Fichier | Points clés |
|---|---|---|
| 1 | `src/bibops/benchmark/compare_architectures.py` | [*] **Pipeline principal** LLM Unique vs Multi-Agents — `ComparaisonResult`, calcul `domain_summary`, latence totale, tokens, coût USD, empreinte CO2e, verdict release |
| 2 | `src/bibops/reporting/charts.py` | [*] Génération PNG matplotlib — bar charts comparatifs, radar sécurité — **les visuels de la présentation** |
| 3 | `src/bibops/evaluation/metrics/composite.py` | [*] `CompositePolicy.evaluate()` — formule : quality×0.40 + security×0.35 + finops×0.10 + latency×0.10 + greenops×0.05 → score/100 ; gates PASS/FAIL (quality≥7, security≥6) |
| 4 | `src/bibops/benchmark/validate_benchmark_output.py` | Validation schéma JSON de sortie (clés : `schema_version`, `config`, `summary`, `quality`, `security`, `composite`, `details`) |

**Questions jury** : Pourquoi quality×0.40 et security×0.35 — justification des pondérations ? Que signifie le verdict release PASS/FAIL ? Comment le coût USD et l'empreinte CO2e sont-ils calculés ? Quel est le résultat global : LLM Unique ou Multi-Agents est-il meilleur et pourquoi ?

---

### Moteur d'évaluation — Contexte résultats (45 min)

| Fichier | Points clés |
|---|---|
| `src/bibops/evaluation/judges/llm_judge.py` | `LLMJudge`, `JudgeVerdict(score: float, justification: str)`, `score(criterion, question, answer)` — primitive générique utilisée dans A/B |
| `src/bibops/evaluation/judges/llm_professor.py` | `LLMProfessor` — wraps `LLMJudge` + contexte RCA IT support, persistance SQLite, batch `evaluer_tickets_en_attente()` |
| `src/bibops/evaluation/scoring/thresholds.py` | `ScoreThreshold`, `ScoreVerdict`, `load_thresholds()`, `evaluate_score()` — seuils PASS/WARN/FAIL |
| `src/bibops/evaluation/registry.py` | `EvaluatorRegistry` — orchestre `QualityEvaluator` + `SecurityLLMInspectorAdapter` en parallèle, merge les résultats |

**Questions jury** : Quelle est la différence entre `LLMJudge` (primitif générique) et `LLMProfessor` (spécifique IT Support) ? Comment `EvaluatorRegistry` orchestre-t-il les deux évaluateurs en parallèle ?

---

## Fichiers à parcourir rapidement (skim)

| Fichier | Pourquoi le parcourir |
|---|---|
| `src/bibops/benchmark/core.py` | `run_benchmark()` — boucle de base qui lit CSV, appelle LLM, demande feedback, écrit JSON |
| `src/bibops/evaluation/result_schema.py` | `EvaluationResult` — structure JSON de sortie des benchmarks |
| `src/bibops/evaluation/config.py` | Constantes d'évaluation (gates, seuils par défaut) |
| `src/bibops/evaluation/judges/rule_engine.py` | `EvaluationEngine` — scoring déterministe sans LLM (error/feedback/speed/token/F1) |
| `src/bibops/evaluation/rca.py` | Root Cause Analysis — enrichit le contexte du juge avec info IT |
| `src/bibops/evaluation/metrics/consistency.py` | Cohérence multi-réponses (détecte les contradictions entre appels) |
| `src/bibops/evaluation/reporting/regression.py` | Détection de régression entre deux runs benchmark |
| `src/common/config.py` | `COPILOT_BASE_URL`, modèles par défaut, `OUTPUT_DIR` |
| `src/bibops/benchmark/local_kaggle_exam.py` | Évaluation Kaggle — compare contre un ground truth externe |

---

## Résultats à connaître (lire les JSON)

| Fichier de données | Ce qu'il contient |
|---|---|
| `data/outputs/benchmark/comparison_results.json` | [*] **Résultats principaux** : LLM Unique vs Multi-Agents, scores par dimension |
| `data/outputs/benchmark/ab_llm_resultat.json` | Résultats du A/B test par juge LLM |
| `data/outputs/benchmark/ab_llm_statements_result.json` | Résultats A/B avec statements |
| `data/outputs/benchmark/ab_user_resultat.json` | Résultats du A/B test utilisateur |
| `data/outputs/benchmark/position_bias_resultat.json` | Taux de biais détecté (si le juge favorise A ou B systématiquement) |
| `data/outputs/benchmark/charts/` | Graphiques PNG générés — **les visuels de la soutenance** |

---

## Résumé — fichiers critiques

```
README.md                                        ← pitch intro jury
src/bibops/benchmark/ab_test_llm.py              ← A/B test LLM
src/bibops/benchmark/ab_test_llm_statements.py   ← prompts juge A/B
src/bibops/benchmark/ab_test_user.py             ← A/B utilisateur
src/bibops/benchmark/position_bias.py            ← biais de position
src/bibops/benchmark/compare_architectures.py    ← résultats principaux
src/bibops/reporting/charts.py                   ← visuels résultats
src/bibops/evaluation/metrics/composite.py       ← formule de scoring
src/bibops/evaluation/judges/llm_judge.py        ← juge LLM primitif
src/bibops/evaluation/judges/llm_professor.py    ← juge IT Support
data/outputs/benchmark/comparison_results.json   ← résultats à citer
```

---

## Questions probables du jury

- Quel est le problème que BibOps résout pour Michelin et pourquoi comparer deux architectures ?
- Comment fonctionne le A/B test LLM — comment le juge LLM tranche-t-il entre les deux réponses ?
- Qu'est-ce que le biais de position et qu'a-t-on observé dans les résultats ?
- Quelle architecture gagne (LLM Unique vs Multi-Agents) et sur quels critères ?
- Comment `CompositePolicy` calcule-t-il le score final et quels sont les gates PASS/FAIL ?
- Pourquoi quality×0.40 et security×0.35 — justification de ces pondérations ?
- Quelle est la différence entre le A/B test LLM et le A/B test utilisateur ?
- Quelle est la différence de rôle entre `LLMJudge` et `LLMProfessor` ?
- Comment `EvaluatorRegistry` orchestre-t-il les évaluateurs en parallèle ?
- Que signifie le verdict release PASS/FAIL dans le rapport de comparaison ?
