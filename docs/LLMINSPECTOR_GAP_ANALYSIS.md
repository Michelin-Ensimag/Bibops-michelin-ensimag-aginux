# LLMInspector vs BibOps — Gap Analysis Architecture & Sécurité

Date: 2026-04-21
Auteur: Audit technique (Architecte IA / Sécurité LLM)

## 0) Périmètre analysé

- Référentiel cible Michelin: `LLMInspector-main/`
- Référentiel projet: `src/bibops/evaluation/` + `scripts/benchmark/compare_architectures.py`

Objectif: comparer l’architecture d’évaluation, identifier les écarts sécurité/conformité, et proposer un plan d’intégration réaliste avant soutenance.

---

## 1) Philosophie & Architecture

### 1.1 BibOps (actuel): logique orientée "runner" + juge monolithique

Constats:
- Le cœur BibOps combine principalement:
  - un juge LLM unique `LLMProfessor` (note + justification),
  - un discriminateur RAGAS simplifié (3 métriques),
  - des agrégations FinOps/Latence/GreenOps dans le script de benchmark.
- Le pipeline principal de comparaison (`LLM unique` vs `Système multi-agents`) est centralisé dans un script procédural.

Conséquence architecture:
- Forte efficacité pour des expérimentations rapides.
- Faible extensibilité native pour ajouter des inspecteurs sécurité spécialisés (PII, prompt injection, secrets, URLs malveillantes, etc.) sans alourdir `llm_judge.py`.

### 1.2 LLMInspector: façade modulaire + catalogue de métriques piloté par configuration

Constats:
- LLMInspector orchestre des modules dédiés via une façade (`alignment`, `adversarial`, `evaluate`, `rag_testset_gen`, `rag_evaluate`).
- Le choix des métriques est externalisé dans `config.ini` (liste `Metrics` + `thresholds`) et non figé dans un prompt unique.

Conséquence architecture:
- Pattern de type "inspecteurs spécialisés" avec activation par config (registry implicite par liste de métriques).
- Meilleure industrialisation: ajout/retrait d’un contrôle via configuration + seuils, sans réécrire toute l’orchestration.

### 1.3 Différence fondamentale de design pattern

- **BibOps**: "un juge pour tout" + quelques métriques codées en dur.
- **LLMInspector**: "suite d’inspecteurs" spécialisés, déclenchés de façon modulaire/configurable.

Conclusion:
- Pour atteindre un niveau production open-source Michelin, BibOps doit évoluer d’un modèle monolithique vers un modèle d’**évaluateurs composables**.

---

## 2) Gap Analysis — Sécurité & Conformité

Lecture demandée: "quelles dimensions LLMInspector couvre et que BibOps ne couvre pas aujourd’hui dans son juge".

### 2.1 Couverture actuelle de BibOps (résumé)

Présent:
- Qualité fonctionnelle (note globale LLMProfessor)
- RAGAS simplifié: faithfulness/relevance/context (Discriminator)
- FinOps (tokens/coût), Latence, GreenOps

Partiel:
- Robustesse adversariale surtout via boucle d’itérations, mais pas via scanners sécurité dédiés.

Absent (dans le juge actuel):
- PII/Secrets/Prompt Injection/Toxicité/Biais/URLs malveillantes/NoRefusal/Factual consistency de sécurité, etc.

### 2.2 Matrice des écarts (exhaustive sécurité/compliance)

| Dimension sécurité/compliance | LLMInspector | BibOps actuel | Écart |
|---|---|---|---|
| Détection PII | Oui (`pii_detection`, Presidio) | Non | Critique |
| Prompt injection (entrée) | Oui (`question_promptInjection`) | Non | Critique |
| Secrets / tokens en entrée | Oui (`question_secrets`, regex Bearer) | Non | Critique |
| Toxicité entrée/sortie | Oui (`question_toxicity`, `answer_toxicity`) | Non | Critique |
| Ban topics / contenus interdits | Oui (`answer_banTopics`) | Non | Majeur |
| Ban substrings jailbreak/social engineering | Oui (`answer_banSubstrings`) | Non | Majeur |
| URLs malveillantes | Oui (`answer_maliciousURLs`) | Non | Critique |
| Vérification refus de requêtes dangereuses | Oui (`answer_noRefusal`) | Non | Critique |
| Biais | Oui (`answer_bias`) | Non | Majeur |
| Cohérence factuelle de sûreté | Oui (`answer_factualConsistency`) | Non | Majeur |
| Pertinence scanner sécurité (output relevance) | Oui (`answer_relevance`) | Non | Majeur |
| Détection code suspect (input/output) | Oui (`question_code`, `answer_code`, `question_banCode`) | Non | Majeur |
| Détection gibberish | Oui (`question_gibberish`, `answer_gibberish`) | Non | Moyen |
| Harmfulness / maliciousness (RAG critique) | Oui | Non explicite | Majeur |
| Language consistency | Oui (`answer_language_same`) | Non | Mineur à moyen |
| Sensitive entities en sortie | Oui (`answer_senstivity_detect`) | Non | Majeur |

### 2.3 Remarque importante

LLMInspector couvre bien plus de dimensions, mais certaines implémentations doivent être vérifiées avant adoption directe (ex: incohérences de scanner dans certaines méthodes). Donc l’intégration doit être **encadrée par des tests de non-régression**.

---

## 3) Compatibilité — Recoder dans `llm_judge.py` vs intégrer LLMInspector

### Option A — Recoder les concepts LLMInspector dans `llm_judge.py`

Avantages:
- Contrôle total sur le code BibOps.
- Surface de dépendances externe plus faible.

Inconvénients:
- Coût élevé avant soutenance (beaucoup de dimensions à reproduire).
- Risque de régression élevé.
- Résultat potentiellement moins crédible qu’un alignement direct avec un standard Michelin existant.

### Option B — Importer LLMInspector comme dépendance (adapter dans pipeline BibOps)

Avantages:
- Alignement direct avec le framework Michelin.
- Gain rapide en couverture sécurité/compliance.
- Réutilisabilité plus forte pour future reprise industrielle.

Inconvénients:
- Dépendances lourdes (ragas, llm_guard, presidio, transformers, etc.).
- Nécessite adaptation de schéma I/O (CSV/JSON BibOps vs DataFrame attendu).
- Certaines parties doivent être "sandboxées" pour éviter de casser le pipeline benchmark principal.

### Recommandation

Approche **hybride** (recommandée):
- Garder la pipeline BibOps (`compare_architectures.py`) comme orchestrateur métier.
- Ajouter un **adapter LLMInspector** pour les dimensions sécurité/compliance.
- Ne pas surcharger `llm_judge.py` avec toute la logique sécurité.

Pourquoi:
- Time-to-value court avant soutenance.
- Alignement Michelin explicite.
- Architecture extensible et propre (séparation des responsabilités).

---

## 4) Roadmap Soutenance (3 Quick Wins concrets)

## Quick Win 1 — Introduire une interface d’évaluateur modulaire

Objectif:
- Découpler qualité, sécurité, coût, latence, carbone.

Action:
- Définir un contrat commun (ex: `Evaluator.evaluate(ticket, answer, context) -> dict`).

Exemple d’architecture:

```python
class BaseEvaluator(Protocol):
    def evaluate(self, sample: dict) -> dict: ...

class QualityEvaluatorBibOps(BaseEvaluator): ...
class SecurityEvaluatorLLMInspector(BaseEvaluator): ...
class FinOpsEvaluator(BaseEvaluator): ...
class GreenOpsEvaluator(BaseEvaluator): ...
```

Résultat attendu:
- Pipeline plug-and-play pour ajouter/retirer un inspecteur sans toucher au reste.

## Quick Win 2 — Brancher un Security Adapter LLMInspector sur les sorties BibOps

Objectif:
- Évaluer chaque réponse BibOps avec les contrôles sécurité clés LLMInspector.

Action:
- Construire un adaptateur qui convertit chaque ticket/réponse en DataFrame attendu par `EvalMetrics`.
- Activer un sous-ensemble prioritaire: `pii_detection`, `question_promptInjection`, `question_secrets`, `answer_maliciousURLs`, `answer_noRefusal`, `answer_toxicity`, `question_toxicity`.

Résultat attendu:
- Nouveau bloc "Security Scorecard" dans le JSON final de benchmark.

## Quick Win 3 — Ajouter un score composite et un garde-fou de release

Objectif:
- Passer d’un benchmark descriptif à une décision exploitable (go/no-go).

Action:
- Définir un score composite pondéré: `Qualité + Sécurité + Coût + Latence + CO2`.
- Ajouter des seuils éliminatoires (ex: PII > seuil, prompt injection risk > seuil => échec automatique).

Exemple de règles:

```text
if security.prompt_injection_risk > 0.5: FAIL
if security.pii_detected is True: FAIL
if quality.score_mean < 7.0: FAIL
```

Résultat attendu:
- Un verdict automatique de conformité avant démonstration/soutenance.

---

## 5) Cible d’architecture recommandée (post-gap)

```text
compare_architectures.py
  ├── Generation layer
  │     ├── LLM Unique
  │     └── Multi-Agents (lancer_agent)
  ├── Evaluation layer
  │     ├── QualityEvaluatorBibOps (LLM judge + RAGAS simplifié)
  │     ├── SecurityEvaluatorLLMInspector (adapter)
  │     ├── FinOpsEvaluator
  │     ├── LatencyEvaluator
  │     └── GreenOpsEvaluator
  └── Reporting layer
        ├── comparative table
        ├── score composite
        └── go/no-go policy
```

---

## 6) Éléments de preuve (code)

- Orchestration modulaire LLMInspector: `LLMInspector-main/llm_inspector/llminspector.py`
- Catalogue de métriques + seuils: `LLMInspector-main/config.ini`
- Scanners sécurité/compliance: `LLMInspector-main/llm_inspector/eval_metrics.py`
- Juge monolithique BibOps: `src/bibops/evaluation/llm_judge.py`
- Discriminateur BibOps (3 métriques): `src/bibops/evaluation/discriminator.py`
- Benchmark BibOps (quality/latency/cost/CO2): `scripts/benchmark/compare_architectures.py`
- GreenOps actuel: `src/bibops/evaluation/greenops.py`

---

## 7) Verdict d’audit

BibOps est déjà solide pour la comparaison architecturelle (LLM unique vs agentique) et la mesure opérationnelle (latence, coût, carbone). En revanche, **l’écart principal avec LLMInspector est la profondeur sécurité/compliance**.

Pour atteindre un niveau "production-ready Michelin", la priorité n’est pas d’épaissir `llm_judge.py`, mais de **composer** un module sécurité dédié inspiré/adossé à LLMInspector dans la pipeline existante.
