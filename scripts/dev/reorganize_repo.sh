#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

echo "[P0] Preflight"
mkdir -p src/bibops/it_support src/bibops/racing/hub src/bibops/racing/team_client src/bibops/benchmark src/bibops/llm_professor src/bibops/common
mkdir -p data/raw/benchmark data/temp/benchmark data/outputs/benchmark data/fixtures/benchmark
mkdir -p docs/literature docs/notebooks docs/presentations docs/assets/screenshots docs/notebooks/lang_chatbot
mkdir -p data/databases

echo "[P1] Harden .gitignore"
if ! rg -q '^\*\.pyc$' .gitignore; then echo '*.pyc' >> .gitignore; fi
if ! rg -q '^\.ruff_cache/$' .gitignore; then echo '.ruff_cache/' >> .gitignore; fi
if ! rg -q '^logs/$' .gitignore; then echo 'logs/' >> .gitignore; fi
if ! rg -q '^\.DS_Store$' .gitignore; then echo '.DS_Store' >> .gitignore; fi

echo "[P2] Move tracked code into src/bibops"
# IT support
for src_file in __init__.py baseSQL.py maestro.py memoire_RAG.py memoire_courte.py outils.py serveur_mcp.py; do
  case "$src_file" in
    baseSQL.py) dst_file="database.py" ;;
    maestro.py) dst_file="agent.py" ;;
    memoire_RAG.py) dst_file="rag.py" ;;
    memoire_courte.py) dst_file="memory.py" ;;
    outils.py) dst_file="tools.py" ;;
    serveur_mcp.py) dst_file="mcp_server.py" ;;
    __init__.py) dst_file="__init__.py" ;;
  esac
  git mv -f "src/agents/$src_file" "src/bibops/it_support/$dst_file"
done

# Racing
for src_file in __init__.py demo.py experts.py graph.py start_arena.py state.py supervisor.py; do
  git mv -f "src/agents_racing/$src_file" "src/bibops/racing/$src_file"
done
for src_file in __init__.py race_engine.py rag_service.py server.py; do
  git mv -f "src/agents_racing/hub/$src_file" "src/bibops/racing/hub/$src_file"
done
git mv -f "src/agents_racing/hub/ingest_racing.py" "src/bibops/racing/hub/ingest.py"
for src_file in __init__.py graph.py main.py nodes.py state_tools.py; do
  git mv -f "src/agents_racing/team_client/$src_file" "src/bibops/racing/team_client/$src_file"
done

# Benchmark
git mv -f src/benchmark/__init__.py src/bibops/benchmark/__init__.py
git mv -f src/benchmark/benchmark.py src/bibops/benchmark/core.py
git mv -f src/benchmark/benchmark_mcp_tools.py src/bibops/benchmark/mcp_tools.py
git mv -f src/benchmark/benchmark_pipeline.py src/bibops/benchmark/pipeline.py
git mv -f src/benchmark/ab_test_llm.py src/bibops/benchmark/ab_test_llm.py
git mv -f src/benchmark/ab_test_user.py src/bibops/benchmark/ab_test_user.py
git mv -f src/benchmark/test-biais-position.py src/bibops/benchmark/test-biais-position.py

# Evaluation
git mv -f src/llm_professor/__init__.py src/bibops/llm_professor/__init__.py
git mv -f src/llm_professor/llm_professor.py src/bibops/llm_professor/llm_judge.py
git mv -f src/llm_professor/rca_engine.py src/bibops/llm_professor/rca.py
git mv -f src/llm_professor/agent_copilot_mcp.py src/bibops/llm_professor/copilot_mcp.py
git mv -f src/llm_professor/agent_langchain_mcp.py src/bibops/llm_professor/langchain_mcp.py
git mv -f src/llm_professor/config_evaluation.py src/bibops/llm_professor/config_evaluation.py

# Untracked-but-important llm_professor modules from recent refactor
if [ -f src/llm_professor/adversarial_loop.py ]; then
  mv -f src/llm_professor/adversarial_loop.py src/bibops/llm_professor/adversarial.py
fi
if [ -f src/llm_professor/discriminator.py ]; then
  mv -f src/llm_professor/discriminator.py src/bibops/llm_professor/discriminator.py
fi

echo "[P3] Rewrite Python imports to src.bibops.*"
find . -type f -name '*.py' -not -path './.git/*' -print0 | xargs -0 perl -pi -e 's/src\.agents_racing/src.bibops.racing/g; s/src\.llm_professor/src.bibops.llm_professor/g; s/src\.benchmark/src.bibops.benchmark/g; s/src\.agents/src.bibops.it_support/g;'

echo "[P3b] Normalize benchmark data paths"
# Inputs
find src scripts -type f -name '*.py' -print0 | xargs -0 perl -pi -e "s#data', 'benchmark', 'tickets_scenario_1\\.csv#data', 'raw', 'benchmark', 'tickets_scenario_1.csv#g"
# Temp outputs
find src scripts -type f -name '*.py' -print0 | xargs -0 perl -pi -e "s#data', 'benchmark', 'ab_llm_resultat_temp\\.json#data', 'temp', 'benchmark', 'ab_llm_resultat_temp.json#g"
find src scripts -type f -name '*.py' -print0 | xargs -0 perl -pi -e "s#data', 'benchmark', 'position_biais_resultat_temp\\.json#data', 'temp', 'benchmark', 'position_biais_resultat_temp.json#g"
# Final outputs (JSON + charts)
find src scripts -type f -name '*.py' -print0 | xargs -0 perl -pi -e "s#data', 'benchmark', '([a-zA-Z0-9_\-]+\\.json)#data', 'outputs', 'benchmark', '\\1#g"
find src scripts -type f -name '*.py' -print0 | xargs -0 perl -pi -e "s#data', 'benchmark', '([a-zA-Z0-9_\-]+\\.png)#data', 'outputs', 'benchmark', '\\1#g"

# Special case: fake eval dataset should be a fixture
find src scripts -type f -name '*.py' -print0 | xargs -0 perl -pi -e "s#data', 'outputs', 'benchmark', 'tickets_evalues_fake\\.json#data', 'fixtures', 'benchmark', 'tickets_evalues_fake.json#g"

echo "[P4] Remove legacy tracked folders"
git rm -r src/agents src/agents_racing src/benchmark src/llm_professor 2>/dev/null || true

echo "[P5] Reorganize tracked data/"
git mv -f data/benchmark/tickets_scenario_1.csv data/raw/benchmark/
git mv -f data/benchmark/ab_llm_resultat_temp.json data/temp/benchmark/
git mv -f data/benchmark/position_biais_resultat_temp.json data/temp/benchmark/
git mv -f data/benchmark/tickets_evalues_fake.json data/fixtures/benchmark/
for f in \
  ab_llm_resultat.json \
  ab_user_resultat.json \
  benchmark_copilot.json \
  benchmark_copilot_mcp.json \
  benchmark_langchain_mcp.json \
  benchmark_mcp.json \
  benchmark_mcp_tools.json \
  graphique_1_score_par_modele.png \
  graphique_2_latence_vs_score.png \
  graphique_3_taux_reussite_outils.png \
  position_bias_resultat.json \
  tickets_evalues.json \
  tickets_evalues_scores.json
  do
  git mv -f "data/benchmark/$f" "data/outputs/benchmark/$f"
done

echo "[P6] Reorganize docs/"
# tracked docs files
git mv -f "docs/2025-11_PENTRE_Michelin_Bibops.pdf" docs/literature/
git mv -f "docs/2512.14982v1.pdf" docs/literature/
git mv -f "docs/Knowledge graph - Wikipedia.pdf" docs/literature/
git mv -f "docs/docu_widad.pdf" docs/literature/
git mv -f "docs/analyse_d_AGENT_ia.ipynb" docs/notebooks/
git mv -f "docs/doc_Akram.ipynb" docs/notebooks/
git mv -f "docs/slides.pdf" docs/presentations/slides.pdf

# tracked lang-chatbot artifacts: code to notebooks area, vector DB to data/databases
git mv -f docs/lang-chatbot/lang-agent-maestro.py docs/notebooks/lang_chatbot/lang-agent-maestro.py
git mv -f docs/lang-chatbot/lang-gen.py docs/notebooks/lang_chatbot/lang-gen.py
git mv -f docs/lang-chatbot/main.py docs/notebooks/lang_chatbot/main.py
git mv -f docs/lang-chatbot/outils.py docs/notebooks/lang_chatbot/outils.py
git mv -f docs/lang-chatbot/chatbot_article_dataset data/databases/

# untracked docs artifacts
mkdir -p docs/assets/screenshots
if [ -d docs/image_GAN ]; then mv docs/image_GAN docs/assets/screenshots/gan; fi
if [ -d docs/image_GAN_2 ]; then mv docs/image_GAN_2 docs/assets/screenshots/gan_2; fi
if [ -f "docs/A05 Injection - OWASP Top 10:2025.pdf" ]; then mv "docs/A05 Injection - OWASP Top 10:2025.pdf" docs/literature/; fi
if [ -f docs/PRESENTATION_RACING.md ]; then mv docs/PRESENTATION_RACING.md docs/presentations/; fi

# adjust references mentioning old modules and old data/doc paths in markdown/notebooks scripts
find docs scripts src tests -type f \( -name '*.md' -o -name '*.py' -o -name '*.ipynb' \) -print0 | xargs -0 perl -pi -e 's/src\/agents_racing/src\/bibops\/racing/g; s/src\/llm_professor/src\/bibops\/llm_professor/g; s/src\/benchmark/src\/bibops\/benchmark/g; s/src\/agents/src\/bibops\/it_support/g; s/data\/benchmark\/tickets_scenario_1\.csv/data\/raw\/benchmark\/tickets_scenario_1.csv/g; s/data\/benchmark\/ab_llm_resultat_temp\.json/data\/temp\/benchmark\/ab_llm_resultat_temp.json/g; s/data\/benchmark\/position_biais_resultat_temp\.json/data\/temp\/benchmark\/position_biais_resultat_temp.json/g; s/data\/benchmark\//data\/outputs\/benchmark\//g; s/docs\/lang-chatbot\/chatbot_article_dataset/data\/databases\/chatbot_article_dataset/g;'
# fix fixture replacement in text refs if needed
find docs scripts src tests -type f \( -name '*.md' -o -name '*.py' -o -name '*.ipynb' \) -print0 | xargs -0 perl -pi -e 's/data\/outputs\/benchmark\/tickets_evalues_fake\.json/data\/fixtures\/benchmark\/tickets_evalues_fake.json/g;'

echo "[P7] Local cache cleanup"
find . -type d -name '__pycache__' -prune -exec rm -rf {} +

# lightweight integrity checks
rg -n "src\\.agents_racing|src\\.agents\\b|src\\.benchmark|src\\.llm_professor" src scripts tests conftest.py || true
rg -n "data/benchmark" src scripts tests docs || true

echo "Done."
