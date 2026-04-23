# 🏎️ BibOps - Banc d'Évaluation de LLMs pour le Support IT

BibOps est un banc d'évaluation orienté support IT qui compare deux approches sur les mêmes tickets: **LLM unique (zero-shot)** vs **système multi-agents (outils + RAG)**. Le framework mesure automatiquement la **qualité**, la **latence**, le **coût d'inférence (FinOps)** et l'**empreinte carbone estimée (GreenOps)** pour faciliter une reprise industrielle chez Michelin.

## Prérequis

- Python **3.12** recommandé
- Environnement virtuel Python
- Ollama local démarré (modèle local disponible, ex: `phi3:latest`)
- (Optionnel mais recommandé pour le juge LLM) Proxy OpenAI-compatible/Copilot actif

Variables d'environnement utiles:

- `COPILOT_API_BASE_URL` (ex: `http://127.0.0.1:4141/v1`)
- `COPILOT_API_URL` (ex: `http://127.0.0.1:4141/v1/chat/completions`)
- `COPILOT_API_KEY`

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Guide Rapide (Quick Start)

### 1) Préparer un CSV de tickets

Le CSV doit contenir au minimum les colonnes:

- `id`
- `contexte`
- `ticket`

Exemple de fichier d'entrée:

- `data/raw/benchmark/tickets_scenario_1.csv`

### 2) Lancer la comparaison architecturale

```bash
python scripts/benchmark/compare_architectures.py \
  --input-csv data/raw/benchmark/tickets_scenario_1.csv \
  --max-tickets 20
```

### 3) Lire les résultats

- Tableau comparatif affiché en console:
  - Score Moyen
  - Latence Totale
  - Coût USD
  - Empreinte gCO2e
- Rapport détaillé sauvegardé dans:
  - `data/outputs/benchmark/comparison_results.json`

## Structure du projet

```text
src/bibops/
├── benchmark/
│   ├── core.py
│   ├── pipeline.py
│   ├── mcp_tools.py
│   └── ab_test_llm.py
├── evaluation/
│   ├── llm_judge.py
│   ├── greenops.py
│   ├── run_kaggle_exam.py
│   └── run_local_kaggle_exam.py
├── it_support/
│   ├── agent.py
│   ├── tools.py
│   ├── rag.py
│   └── mcp_server.py
└── racing/
```

## Sorties principales

- `data/outputs/benchmark/comparison_results.json`
- `data/outputs/benchmark/*.json`

## Objectif de reprise Michelin

Ce dépôt est structuré pour permettre à une équipe Michelin de:

1. brancher un nouveau jeu de tickets CSV,
2. relancer le benchmark en ligne de commande,
3. comparer objectivement architectures et coûts de production.
