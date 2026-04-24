# BibOps Repository Guide (A to Z)

_Generated automatically on 2026-04-22 16:26:42_

## 1) Scope

- Total files analyzed: **368**
- Git tracked files: **285**
- Git untracked files: **84**
- Python source files: **110**
- Documentation files (`.md/.rst/.ipynb/.pdf`): **35**

This document is meant to help you read the repository end-to-end, understand where each file belongs, and how modules interact.

## 2) Top-Level Organization

| Top Folder | File Count | Purpose |
|---|---:|---|
| `data` | 161 | Databases, fixtures, raw datasets, outputs, temp artifacts. |
| `src` | 67 | Application code (BibOps packages and legacy migration surface). |
| `LLMInspector-main` | 57 | External reference framework cloned locally for comparison. |
| `docs` | 51 | Project documentation, literature, notebooks, presentations. |
| `scripts` | 14 | Operational entrypoints to run benchmarks, MCP, racing demos. |
| `logs` | 7 | Project support files. |
| `tests` | 4 | Automated checks for memory/tools/maestro behavior. |
| `.github` | 1 | CI workflow configuration. |
| `.gitignore` | 1 | Project support files. |
| `PROJECT_STRUCTURE.md` | 1 | Project support files. |
| `README.md` | 1 | Project support files. |
| `conftest.py` | 1 | Project support files. |
| `pyproject.toml` | 1 | Project support files. |
| `requirements.txt` | 1 | Project support files. |

## 3) Technology and File-Type Mix

| Extension | Count |
|---|---:|
| `.png` | 138 |
| `.py` | 110 |
| `.bin` | 24 |
| `.md` | 21 |
| `.json` | 16 |
| `.jpg` | 8 |
| `.log` | 7 |
| `.ipynb` | 6 |
| `.pdf` | 6 |
| `.xlsx` | 6 |
| `[no_ext]` | 5 |
| `.toml` | 3 |
| `.ini` | 2 |
| `.rst` | 2 |
| `.sh` | 2 |
| `.sqlite3` | 2 |
| `.txt` | 2 |
| `.yml` | 2 |
| `.bat` | 1 |
| `.csv` | 1 |

## 4) Internal Interaction Map (Python Imports)

The edges below are inferred from static Python imports between components.

| From Component | To Component | Import Edges |
|---|---|---:|
| `scripts/benchmark` | `src/bibops/evaluation` | 7 |
| `src/bibops/evaluation` | `src/bibops/it_support` | 6 |
| `scripts/benchmark` | `src/bibops/benchmark` | 3 |
| `scripts/dev` | `src/bibops/it_support` | 3 |
| `tests` | `src/bibops/it_support` | 3 |
| `scripts/benchmark` | `src/bibops/it_support` | 2 |
| `scripts/racing` | `src/bibops/racing` | 2 |
| `src/bibops/benchmark` | `src/bibops/it_support` | 2 |
| `scripts/copilot` | `src/bibops/evaluation` | 1 |
| `scripts/copilot` | `src/test_copilot_api.py` | 1 |
| `src/bibops/benchmark` | `src/bibops/evaluation` | 1 |

### 4.1 Practical runtime flow (high-level)

1. `scripts/*` launches benchmark/evaluation/racing workflows.
2. `src/bibops/benchmark/*` orchestrates experiments and metrics collection.
3. `src/bibops/it_support/*` provides agent logic, tools, DB access, MCP server.
4. `src/bibops/evaluation/*` computes quality/judge/security/greenops style evaluations.
5. `data/raw` + `data/fixtures` feed runs; `data/outputs` stores benchmark results.

## 5) Component-by-Component Reading Order

1. `README.md`
2. `src/bibops/it_support/agent.py`
3. `src/bibops/it_support/tools.py`
4. `src/bibops/it_support/database.py`
5. `src/bibops/evaluation/llm_judge.py`
6. `src/bibops/evaluation/rule_engine.py`
7. `src/bibops/benchmark/core.py`
8. `src/bibops/benchmark/pipeline.py`
9. `scripts/benchmark/compare_architectures.py`

## 6) Full A-to-Z File Catalog

Every file currently present in the Git scope (tracked + untracked), grouped by component.

### `.github`

- `.github/workflows/ci.yml` (config/script, 0.8 KB, 38 lines) - # CHATGPT

### `.gitignore`

- `.gitignore` (text, 0.1 KB, 14 lines) - # Fichiers Mac

### `LLMInspector-main/.gitignore`

- `LLMInspector-main/.gitignore` (text, 0.8 KB, 76 lines) - # from https://github.com/github/gitignore/blob/master/Python.gitignore

### `LLMInspector-main/.gitlab-ci.yml`

- `LLMInspector-main/.gitlab-ci.yml` (config/script, 1.9 KB, 62 lines) - # You can override the included template(s) by including variable overrides

### `LLMInspector-main/.pre-commit-config.yaml`

- `LLMInspector-main/.pre-commit-config.yaml` (config/script, 0.2 KB, 14 lines) - repos:

### `LLMInspector-main/.streamlit`

- `LLMInspector-main/.streamlit/config.toml` (config/script, 0.2 KB, 12 lines) - [client]

### `LLMInspector-main/LICENSE`

- `LLMInspector-main/LICENSE` (text, 11.1 KB, 201 lines) - Apache License

### `LLMInspector-main/LLMInspector_main.py`

- `LLMInspector-main/LLMInspector_main.py` (python, 1.3 KB, 40 lines) - Python module.

### `LLMInspector-main/README.md`

- `LLMInspector-main/README.md` (documentation, 3.0 KB, 62 lines) - LLMInspector

### `LLMInspector-main/ci_badges.sh`

- `LLMInspector-main/ci_badges.sh` (config/script, 1.6 KB, 64 lines) - #!/bin/bash

### `LLMInspector-main/config.ini`

- `LLMInspector-main/config.ini` (config/script, 7.9 KB, 216 lines) - #------------------------------

### `LLMInspector-main/docs`

- `LLMInspector-main/docs/Makefile` (text, 0.6 KB, 19 lines) - # Minimal makefile for Sphinx documentation
- `LLMInspector-main/docs/README.md` (documentation, 0.0 KB, 1 lines) - Documentation text file.
- `LLMInspector-main/docs/api.rst` (documentation, 0.2 KB, 12 lines) - .. _temp:
- `LLMInspector-main/docs/assets/images/README.md` (documentation, 0.0 KB, 1 lines) - Documentation text file.
- `LLMInspector-main/docs/assets/images/llminspector_flow_v1.0.png` (binary.png, 214.7 KB) - Binary asset (image/documentation support).
- `LLMInspector-main/docs/conf.py` (python, 6.3 KB, 199 lines) - Configuration file for llm_inspector's documentations.
- `LLMInspector-main/docs/index.rst` (documentation, 0.4 KB, 13 lines) - .. llm_inspector documentation master file, created by
- `LLMInspector-main/docs/llminspector_flow_v1.0.png` (binary.png, 214.7 KB) - Binary asset (image/documentation support).
- `LLMInspector-main/docs/make.bat` (config/script, 0.7 KB, 35 lines) - @ECHO OFF

### `LLMInspector-main/example`

- `LLMInspector-main/example/Data/AdversarialAttack_Data.xlsx` (binary.xlsx, 221.8 KB) - Binary file.
- `LLMInspector-main/example/Data/GenAI_tool_-_Qualitative_Evaluation_V1.0.xlsx` (binary.xlsx, 17.2 KB) - Binary file.
- `LLMInspector-main/example/Data/Golden_data_sample.xlsx` (binary.xlsx, 13.7 KB) - Binary file.
- `LLMInspector-main/example/Data/LLMInspector_Risk_assessment_V1.0.xlsx` (binary.xlsx, 956.4 KB) - Binary file.
- `LLMInspector-main/example/Tutorials/adversarial_example.ipynb` (notebook, 4.2 KB, 167 lines) - Jupyter notebook (7 cells). First markdown: ## Creating Adversarial Test Data
- `LLMInspector-main/example/Tutorials/alignment_example.ipynb` (notebook, 6.0 KB, 157 lines) - Jupyter notebook (8 cells). First markdown: ## Creating Alignment data using Tag Augmentation
- `LLMInspector-main/example/Tutorials/evaluate_example.ipynb` (notebook, 3.3 KB, 97 lines) - Jupyter notebook (7 cells). First markdown: ## Evaluation for any chatbot based application
- `LLMInspector-main/example/Tutorials/rag_example.ipynb` (notebook, 3.5 KB, 105 lines) - Jupyter notebook (8 cells). First markdown: ## RAG TestSet Generation and Evaluation

### `LLMInspector-main/images`

- `LLMInspector-main/images/LLM Evaluation.png` (binary.png, 797.0 KB) - Binary asset (image/documentation support).
- `LLMInspector-main/images/Michelin_logo_image.png` (binary.png, 26.7 KB) - Binary asset (image/documentation support).
- `LLMInspector-main/images/images-logo2 1.png` (binary.png, 5.5 KB) - Binary asset (image/documentation support).
- `LLMInspector-main/images/llminspector_flow_v1.0.jpg` (binary.jpg, 214.7 KB) - Binary asset (image/documentation support).
- `LLMInspector-main/images/white_logo-removebg-preview 1.png` (binary.png, 10.4 KB) - Binary asset (image/documentation support).

### `LLMInspector-main/llm_inspector`

- `LLMInspector-main/llm_inspector/__init__.py` (python, 0.2 KB, 7 lines) - Main module of llm_inspector.
- `LLMInspector-main/llm_inspector/adversarial.py` (python, 4.7 KB, 147 lines) - Python module. [classes=Adversarial]
- `LLMInspector-main/llm_inspector/alignment.py` (python, 25.6 KB, 697 lines) - Python module. [classes=KeywordNotFoundException, Alignment]
- `LLMInspector-main/llm_inspector/alignment_replace_function.py` (python, 0.9 KB, 20 lines) - Python module. [classes=tag_replace]
- `LLMInspector-main/llm_inspector/constants.py` (python, 7677.4 KB, 148800 lines) - Python module.
- `LLMInspector-main/llm_inspector/eval_metrics.py` (python, 70.6 KB, 1593 lines) - Python module. [classes=EvalMetrics]
- `LLMInspector-main/llm_inspector/llminspector.py` (python, 3.1 KB, 96 lines) - Python module. [classes=llminspector]
- `LLMInspector-main/llm_inspector/rag_eval.py` (python, 10.4 KB, 289 lines) - Python module. [classes=RagEval]

### `LLMInspector-main/pages`

- `LLMInspector-main/pages/Documents_links.py` (python, 1.5 KB, 57 lines) - Python module.
- `LLMInspector-main/pages/Metric_Evaluation.py` (python, 19.5 KB, 565 lines) - Python module. [functions=to_excel, load_data, create_bar_chart, gauge_chart]
- `LLMInspector-main/pages/RAG_data_generation.py` (python, 3.6 KB, 113 lines) - Python module. [functions=to_excel, load_documents]
- `LLMInspector-main/pages/adverserial_data_generation.py` (python, 2.5 KB, 84 lines) - Python module. [functions=to_excel, load_data]
- `LLMInspector-main/pages/alignment_data_generation.py` (python, 4.9 KB, 162 lines) - Python module. [functions=to_excel, load_data]
- `LLMInspector-main/pages/welcome_home.py` (python, 1.9 KB, 47 lines) - Python module.

### `LLMInspector-main/pyproject.toml`

- `LLMInspector-main/pyproject.toml` (config/script, 2.6 KB, 128 lines) - [project]

### `LLMInspector-main/req.txt`

- `LLMInspector-main/req.txt` (documentation, 0.6 KB, 32 lines) - ragas==0.1.21

### `LLMInspector-main/setup.py`

- `LLMInspector-main/setup.py` (python, 0.4 KB, 20 lines) - Setup script for llm_inspector.

### `LLMInspector-main/sonar-project.properties`

- `LLMInspector-main/sonar-project.properties` (config/script, 0.1 KB, 2 lines) - sonar.projectKey=DAI_QA_llm_inspector_AY-VbTKHxLVMzU31btSu

### `LLMInspector-main/tests`

- `LLMInspector-main/tests/__init__.py` (python, 0.0 KB, 0 lines) - Package initializer.
- `LLMInspector-main/tests/test_adversarial.py` (python, 0.5 KB, 21 lines) - Automated test module. [functions=test_init, test_adversarial_export]
- `LLMInspector-main/tests/test_alignment.py` (python, 0.8 KB, 37 lines) - Automated test module. [functions=test_init, test_tagaugmentation, test_paraphrasing, test_perturbation]
- `LLMInspector-main/tests/test_evaluate.py` (python, 11.6 KB, 150 lines) - Automated test module. [functions=test_init, test_accuracy_rouge, test_bertscore, test_toxicity_detection]
- `LLMInspector-main/tests/test_rag.py` (python, 0.2 KB, 8 lines) - Automated test module.
- `LLMInspector-main/tests/test_sample/test_adversarialdata.xlsx` (binary.xlsx, 213.8 KB) - Binary file.
- `LLMInspector-main/tests/test_sample/test_alignmentdata.xlsx` (binary.xlsx, 9.2 KB) - Binary file.
- `LLMInspector-main/tests/test_sample/test_config.ini` (config/script, 2.2 KB, 59 lines) - #------------------------------

### `PROJECT_STRUCTURE.md`

- `PROJECT_STRUCTURE.md` (documentation, 1.1 KB, 33 lines) - BibOps Project Structure (Non-Destructive Reorganization)

### `README.md`

- `README.md` (documentation, 2.4 KB, 91 lines) - 🏎️ BibOps - Banc d'Évaluation de LLMs pour le Support IT

### `conftest.py`

- `conftest.py` (python, 1.2 KB, 32 lines) - conftest.py (racine du projet)

### `data/databases`

- `data/databases/bibops.db` (binary.db, 40.0 KB) - Binary database/index artifact used by runtime or vector store.
- `data/databases/chatbot_article_dataset/chroma.sqlite3` (binary.sqlite3, 1916.0 KB) - Binary database/index artifact used by runtime or vector store.
- `data/databases/chatbot_article_dataset/d0ad38b4-70e3-43b2-aeb7-71c33db021a4/data_level0.bin` (binary.bin, 163.7 KB) - Binary database/index artifact used by runtime or vector store.
- `data/databases/chatbot_article_dataset/d0ad38b4-70e3-43b2-aeb7-71c33db021a4/header.bin` (binary.bin, 0.1 KB) - Binary database/index artifact used by runtime or vector store.
- `data/databases/chatbot_article_dataset/d0ad38b4-70e3-43b2-aeb7-71c33db021a4/length.bin` (binary.bin, 0.4 KB) - Binary database/index artifact used by runtime or vector store.
- `data/databases/chatbot_article_dataset/d0ad38b4-70e3-43b2-aeb7-71c33db021a4/link_lists.bin` (text, 0.0 KB, 0 lines) - Text file.
- `data/databases/vectordb/2d703f9c-13bc-427f-8be4-e95885c442af/data_level0.bin` (binary.bin, 313.7 KB) - Binary database/index artifact used by runtime or vector store.
- `data/databases/vectordb/2d703f9c-13bc-427f-8be4-e95885c442af/header.bin` (binary.bin, 0.1 KB) - Binary database/index artifact used by runtime or vector store.
- `data/databases/vectordb/2d703f9c-13bc-427f-8be4-e95885c442af/length.bin` (binary.bin, 0.4 KB) - Binary database/index artifact used by runtime or vector store.
- `data/databases/vectordb/2d703f9c-13bc-427f-8be4-e95885c442af/link_lists.bin` (text, 0.0 KB, 0 lines) - Text file.
- `data/databases/vectordb/4a7843ac-c380-442d-aca3-f86688ce4d10/data_level0.bin` (binary.bin, 3136.7 KB) - Binary database/index artifact used by runtime or vector store.
- `data/databases/vectordb/4a7843ac-c380-442d-aca3-f86688ce4d10/header.bin` (binary.bin, 0.1 KB) - Binary database/index artifact used by runtime or vector store.
- `data/databases/vectordb/4a7843ac-c380-442d-aca3-f86688ce4d10/length.bin` (binary.bin, 3.9 KB) - Binary database/index artifact used by runtime or vector store.
- `data/databases/vectordb/4a7843ac-c380-442d-aca3-f86688ce4d10/link_lists.bin` (text, 0.0 KB, 0 lines) - Text file.
- `data/databases/vectordb/62f0e3e9-1765-453e-b303-201a4f7c550d/data_level0.bin` (binary.bin, 313.7 KB) - Binary database/index artifact used by runtime or vector store.
- `data/databases/vectordb/62f0e3e9-1765-453e-b303-201a4f7c550d/header.bin` (binary.bin, 0.1 KB) - Binary database/index artifact used by runtime or vector store.
- `data/databases/vectordb/62f0e3e9-1765-453e-b303-201a4f7c550d/length.bin` (binary.bin, 0.4 KB) - Binary database/index artifact used by runtime or vector store.
- `data/databases/vectordb/62f0e3e9-1765-453e-b303-201a4f7c550d/link_lists.bin` (text, 0.0 KB, 0 lines) - Text file.
- `data/databases/vectordb/799fc6e4-d3c8-4886-8918-3c226b5a7d91/data_level0.bin` (binary.bin, 1636.7 KB) - Binary database/index artifact used by runtime or vector store.
- `data/databases/vectordb/799fc6e4-d3c8-4886-8918-3c226b5a7d91/header.bin` (binary.bin, 0.1 KB) - Binary database/index artifact used by runtime or vector store.
- `data/databases/vectordb/799fc6e4-d3c8-4886-8918-3c226b5a7d91/length.bin` (binary.bin, 3.9 KB) - Binary database/index artifact used by runtime or vector store.
- `data/databases/vectordb/799fc6e4-d3c8-4886-8918-3c226b5a7d91/link_lists.bin` (text, 0.0 KB, 0 lines) - Text file.
- `data/databases/vectordb/a314078d-c388-4d66-9251-d22870ef531f/data_level0.bin` (binary.bin, 163.7 KB) - Binary database/index artifact used by runtime or vector store.
- `data/databases/vectordb/a314078d-c388-4d66-9251-d22870ef531f/header.bin` (binary.bin, 0.1 KB) - Binary database/index artifact used by runtime or vector store.
- `data/databases/vectordb/a314078d-c388-4d66-9251-d22870ef531f/length.bin` (binary.bin, 0.4 KB) - Binary database/index artifact used by runtime or vector store.
- `data/databases/vectordb/a314078d-c388-4d66-9251-d22870ef531f/link_lists.bin` (text, 0.0 KB, 0 lines) - Text file.
- `data/databases/vectordb/chroma.sqlite3` (binary.sqlite3, 5792.0 KB) - Binary database/index artifact used by runtime or vector store.

### `data/fixtures`

- `data/fixtures/README.md` (documentation, 0.2 KB, 6 lines) - data/fixtures
- `data/fixtures/benchmark/tickets_evalues_fake.json` (data-json, 6.2 KB, 134 lines) - JSON array with 12 items.

### `data/knowledge_base`

- `data/knowledge_base/articles/KB0010356/article.md` (documentation, 1.6 KB, 36 lines) - **Summary**
- `data/knowledge_base/articles/KB0010426/Pasted image.png` (binary.png, 4.3 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010426/Pasted image_1.png` (binary.png, 1.5 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010426/article.md` (documentation, 1.3 KB, 31 lines) - **Summary**
- `data/knowledge_base/articles/KB0010862/AD Screen.png` (binary.png, 77.4 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/AD Screen_1.png` (binary.png, 121.6 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/AD Screen_2.png` (binary.png, 122.1 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/AD-Find.jpg` (binary.jpg, 35.9 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/AD-Object.jpg` (binary.jpg, 51.0 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/AD-PC.jpg` (binary.jpg, 64.8 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/AD-recovery.jpg` (binary.jpg, 62.4 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/ADUC.png` (binary.png, 42.1 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/Attribute Editor.png` (binary.png, 46.1 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/Bitlocker1.png` (binary.png, 119.7 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/Bitlocker1_1.PNG` (binary.png, 26.8 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/Bitlocker1_2.PNG` (binary.png, 41.0 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/Bitlocker1_3.PNG` (binary.png, 41.0 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/Bitlocker1_4.PNG` (binary.png, 27.0 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/Bitlocker2.PNG` (binary.png, 81.7 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/Bitlocker22.PNG` (binary.png, 61.1 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/Bitlocker2_1.PNG` (binary.png, 57.8 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/Bitlocker3.PNG` (binary.png, 74.7 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/Bitlocker3_1.PNG` (binary.png, 70.6 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/Drive Label.png` (binary.png, 46.8 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/Find Computer screen.png` (binary.png, 33.5 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/Navigate to computer location.png` (binary.png, 89.8 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/Object Name.png` (binary.png, 55.7 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/PROP.png` (binary.png, 147.3 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/Pasted Image.png` (binary.png, 43.9 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/Pasted Image_1.png` (binary.png, 43.9 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/Pasted Image_2.png` (binary.png, 0.2 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/Pasted Image_3.png` (binary.png, 43.9 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/Pasted Image_4.png` (binary.png, 0.2 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/Pasted Image_7.png` (binary.png, 43.9 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/Pasted image_10.png` (binary.png, 248.1 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/Pasted image_11.png` (binary.png, 183.2 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/Pasted image_12.png` (binary.png, 160.5 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/Pasted image_5.png` (binary.png, 99.9 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/Pasted image_6.png` (binary.png, 392.5 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/Pasted image_8.png` (binary.png, 194.9 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/Pasted image_9.png` (binary.png, 235.1 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/Properties Screen.png` (binary.png, 65.8 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/String Editor.png` (binary.png, 14.2 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/article.md` (documentation, 5.6 KB, 76 lines) - **Summary**
- `data/knowledge_base/articles/KB0010862/bitloc rcovr.png` (binary.png, 29.3 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/com host.png` (binary.png, 94.3 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/comp.PNG` (binary.png, 209.9 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/find.png` (binary.png, 122.6 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010862/reco pro.png` (binary.png, 115.4 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image.jpg` (binary.jpg, 10.6 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image.png` (binary.png, 10.6 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_1.png` (binary.png, 218.6 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_10.png` (binary.png, 19.2 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_11.png` (binary.png, 9.4 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_12.png` (binary.png, 29.4 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_13.png` (binary.png, 56.1 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_14.png` (binary.png, 43.1 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_15.png` (binary.png, 8.3 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_16.png` (binary.png, 2.8 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_17.png` (binary.png, 29.0 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_18.png` (binary.png, 5.4 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_19.png` (binary.png, 2.3 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_2.png` (binary.png, 23.7 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_20.png` (binary.png, 67.7 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_21.png` (binary.png, 59.5 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_22.png` (binary.png, 26.4 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_23.png` (binary.png, 1.9 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_24.png` (binary.png, 6.2 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_25.png` (binary.png, 3.4 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_26.png` (binary.png, 20.6 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_27.png` (binary.png, 3.6 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_28.png` (binary.png, 3.6 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_29.png` (binary.png, 89.1 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_3.png` (binary.png, 1.3 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_30.png` (binary.png, 1.6 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_31.png` (binary.png, 14.7 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_32.png` (binary.png, 6.1 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_33.png` (binary.png, 10.6 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_34.png` (binary.png, 59.5 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_35.png` (binary.png, 31.2 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_36.png` (binary.png, 29.4 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_37.png` (binary.png, 167.3 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_38.png` (binary.png, 31.2 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_39.png` (binary.png, 8.1 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_4.png` (binary.png, 17.1 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_40.png` (binary.png, 1.3 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_41.png` (binary.png, 22.6 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_42.png` (binary.png, 28.3 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_43.png` (binary.png, 7.1 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_44.png` (binary.png, 4.1 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_45.png` (binary.png, 5.6 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_46.png` (binary.png, 52.7 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_47.png` (binary.png, 2.8 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_48.png` (binary.png, 1.9 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_49.png` (binary.png, 44.1 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_5.png` (binary.png, 42.5 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_50.png` (binary.png, 5.2 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_51.png` (binary.png, 26.4 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_6.png` (binary.png, 17.1 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_7.png` (binary.png, 23.3 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_8.png` (binary.png, 1.5 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/Pasted image_9.png` (binary.png, 89.1 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/article.md` (documentation, 10.5 KB, 146 lines) - **Summary**
- `data/knowledge_base/articles/KB0010879/intranet_1.jpg` (binary.jpg, 284.5 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010879/intranet_2.jpg` (binary.jpg, 180.4 KB) - Binary asset (image/documentation support).
- `data/knowledge_base/articles/KB0010918/article.md` (documentation, 1.2 KB, 29 lines) - **Summary:**
- `data/knowledge_base/articles/KB0010921/article.md` (documentation, 1.7 KB, 36 lines) - **Do not always assume that if the email looks as if it came from a company email that it is genuine, it is VERY easy to spoof email addresses.**
- `data/knowledge_base/doc_md/architecture_vpn.md` (documentation, 0.8 KB, 11 lines) - Spécifications Techniques VPN Michelin (AnyConnect)
- `data/knowledge_base/doc_md/standard_post.md` (documentation, 0.7 KB, 14 lines) - Standards Masterisation et Parc Poste de Travail
- `data/knowledge_base/kb.zip` (binary.zip, 6856.1 KB) - Compressed archive.
- `data/knowledge_base/knowledge_base.json` (data-json, 11.6 KB, 270 lines) - JSON object keys: version, derniere_mise_a_jour, knowledge_base

### `data/outputs`

- `data/outputs/README.md` (documentation, 0.2 KB, 7 lines) - data/outputs
- `data/outputs/benchmark/.gitkeep` (text, 0.0 KB, 0 lines) - Text file.
- `data/outputs/benchmark/ab_llm_resultat.json` (data-json, 4.8 KB, 97 lines) - JSON object keys: modeles, juge, scores, pourcentages, details
- `data/outputs/benchmark/ab_user_resultat.json` (data-json, 8.7 KB, 48 lines) - JSON object keys: modeles, scores, pourcentages, details
- `data/outputs/benchmark/benchmark_copilot.json` (data-json, 4.1 KB, 23 lines) - JSON array with 3 items.
- `data/outputs/benchmark/benchmark_copilot_mcp.json` (data-json, 12.4 KB, 242 lines) - JSON array with 15 items.
- `data/outputs/benchmark/benchmark_langchain_mcp.json` (data-json, 14.3 KB, 242 lines) - JSON array with 15 items.
- `data/outputs/benchmark/benchmark_mcp.json` (data-json, 1.7 KB, 72 lines) - JSON array with 5 items.
- `data/outputs/benchmark/benchmark_mcp_tools.json` (data-json, 1.7 KB, 72 lines) - JSON array with 5 items.
- `data/outputs/benchmark/comparison_results.json` (data-json, 21.7 KB, 521 lines) - JSON object keys: schema_version, generated_at_utc, config, summary, quality, security, composite, details
- `data/outputs/benchmark/graphique_1_score_par_modele.png` (binary.png, 24.5 KB) - Binary asset (image/documentation support).
- `data/outputs/benchmark/graphique_2_latence_vs_score.png` (binary.png, 38.9 KB) - Binary asset (image/documentation support).
- `data/outputs/benchmark/graphique_3_taux_reussite_outils.png` (binary.png, 29.4 KB) - Binary asset (image/documentation support).
- `data/outputs/benchmark/position_bias_resultat.json` (data-json, 38.1 KB, 859 lines) - JSON object keys: summary, details
- `data/outputs/benchmark/tickets_evalues.json` (data-json, 8.3 KB, 90 lines) - JSON array with 8 items.
- `data/outputs/benchmark/tickets_evalues_scores.json` (data-json, 6.0 KB, 248 lines) - JSON object keys: date_evaluation, total_tickets, tickets_evalues, statistiques_par_modele

### `data/raw`

- `data/raw/README.md` (documentation, 0.2 KB, 7 lines) - data/raw
- `data/raw/benchmark/tickets_scenario_1.csv` (data-csv, 4.7 KB, 41 lines) - CSV columns: id, contexte, ticket

### `data/runtime`

- `data/runtime/README.md` (documentation, 0.2 KB, 10 lines) - data/runtime

### `data/temp`

- `data/temp/benchmark/ab_llm_resultat_temp.json` (data-json, 4.7 KB, 97 lines) - JSON object keys: modeles, juge, scores, pourcentages, details
- `data/temp/benchmark/position_biais_resultat_temp.json` (data-json, 38.2 KB, 859 lines) - JSON object keys: summary, details

### `docs/LLMINSPECTOR_GAP_ANALYSIS.md`

- `docs/LLMINSPECTOR_GAP_ANALYSIS.md` (documentation, 9.6 KB, 229 lines) - LLMInspector vs BibOps — Gap Analysis Architecture & Sécurité

### `docs/architecture`

- `docs/architecture/REORGANIZATION_MAP.md` (documentation, 1.6 KB, 36 lines) - Reorganization Map

### `docs/assets`

- `docs/assets/screenshots/gan/Screenshot 2026-04-04 at 09.08.18.png` (binary.png, 528.5 KB) - Binary asset (image/documentation support).
- `docs/assets/screenshots/gan/Screenshot 2026-04-04 at 09.08.24.png` (binary.png, 593.4 KB) - Binary asset (image/documentation support).
- `docs/assets/screenshots/gan/Screenshot 2026-04-04 at 09.08.31.png` (binary.png, 599.8 KB) - Binary asset (image/documentation support).
- `docs/assets/screenshots/gan/Screenshot 2026-04-04 at 09.08.37.png` (binary.png, 617.0 KB) - Binary asset (image/documentation support).
- `docs/assets/screenshots/gan/Screenshot 2026-04-04 at 09.08.42.png` (binary.png, 662.7 KB) - Binary asset (image/documentation support).
- `docs/assets/screenshots/gan/Screenshot 2026-04-04 at 09.08.49.png` (binary.png, 522.1 KB) - Binary asset (image/documentation support).
- `docs/assets/screenshots/gan/Screenshot 2026-04-04 at 09.08.53.png` (binary.png, 700.4 KB) - Binary asset (image/documentation support).
- `docs/assets/screenshots/gan/Screenshot 2026-04-04 at 09.08.58.png` (binary.png, 708.5 KB) - Binary asset (image/documentation support).
- `docs/assets/screenshots/gan/Screenshot 2026-04-04 at 09.09.03.png` (binary.png, 677.1 KB) - Binary asset (image/documentation support).
- `docs/assets/screenshots/gan/Screenshot 2026-04-04 at 09.09.08.png` (binary.png, 694.1 KB) - Binary asset (image/documentation support).
- `docs/assets/screenshots/gan/Screenshot 2026-04-04 at 09.09.13.png` (binary.png, 692.9 KB) - Binary asset (image/documentation support).
- `docs/assets/screenshots/gan/Screenshot 2026-04-04 at 09.09.16.png` (binary.png, 604.2 KB) - Binary asset (image/documentation support).
- `docs/assets/screenshots/gan/Screenshot 2026-04-04 at 09.09.27.png` (binary.png, 607.0 KB) - Binary asset (image/documentation support).
- `docs/assets/screenshots/gan/Screenshot 2026-04-04 at 09.09.31.png` (binary.png, 636.6 KB) - Binary asset (image/documentation support).
- `docs/assets/screenshots/gan/Screenshot 2026-04-04 at 09.09.34.png` (binary.png, 668.2 KB) - Binary asset (image/documentation support).
- `docs/assets/screenshots/gan/Screenshot 2026-04-04 at 09.09.37.png` (binary.png, 627.6 KB) - Binary asset (image/documentation support).
- `docs/assets/screenshots/gan/Screenshot 2026-04-04 at 09.09.41.png` (binary.png, 699.4 KB) - Binary asset (image/documentation support).
- `docs/assets/screenshots/gan/Screenshot 2026-04-04 at 09.09.43.png` (binary.png, 729.0 KB) - Binary asset (image/documentation support).
- `docs/assets/screenshots/gan/Screenshot 2026-04-04 at 09.09.47.png` (binary.png, 624.5 KB) - Binary asset (image/documentation support).
- `docs/assets/screenshots/gan/Screenshot 2026-04-04 at 09.09.51.png` (binary.png, 587.9 KB) - Binary asset (image/documentation support).
- `docs/assets/screenshots/gan/Screenshot 2026-04-04 at 09.09.54.png` (binary.png, 680.3 KB) - Binary asset (image/documentation support).
- `docs/assets/screenshots/gan/Screenshot 2026-04-04 at 09.09.57.png` (binary.png, 608.6 KB) - Binary asset (image/documentation support).
- `docs/assets/screenshots/gan/Screenshot 2026-04-04 at 09.10.01.png` (binary.png, 598.0 KB) - Binary asset (image/documentation support).
- `docs/assets/screenshots/gan_2/Screenshot 2026-03-20 at 23.42.23.png` (binary.png, 338.7 KB) - Binary asset (image/documentation support).
- `docs/assets/screenshots/gan_2/Screenshot 2026-04-10 at 13.04.38.png` (binary.png, 6.6 KB) - Binary asset (image/documentation support).
- `docs/assets/screenshots/gan_2/Screenshot 2026-04-10 at 15.24.50.png` (binary.png, 552.0 KB) - Binary asset (image/documentation support).
- `docs/assets/screenshots/gan_2/Screenshot 2026-04-10 at 15.24.54.png` (binary.png, 573.7 KB) - Binary asset (image/documentation support).
- `docs/assets/screenshots/gan_2/Screenshot 2026-04-10 at 15.24.58.png` (binary.png, 529.4 KB) - Binary asset (image/documentation support).
- `docs/assets/screenshots/gan_2/Screenshot 2026-04-10 at 15.25.02.png` (binary.png, 426.1 KB) - Binary asset (image/documentation support).
- `docs/assets/screenshots/gan_2/Screenshot 2026-04-10 at 15.25.04.png` (binary.png, 488.4 KB) - Binary asset (image/documentation support).
- `docs/assets/screenshots/gan_2/Screenshot 2026-04-10 at 15.25.19.png` (binary.png, 516.5 KB) - Binary asset (image/documentation support).
- `docs/assets/screenshots/gan_2/Screenshot 2026-04-10 at 15.25.24.png` (binary.png, 548.5 KB) - Binary asset (image/documentation support).
- `docs/assets/screenshots/gan_2/Screenshot 2026-04-10 at 15.25.27.png` (binary.png, 491.9 KB) - Binary asset (image/documentation support).
- `docs/assets/screenshots/gan_2/Screenshot 2026-04-10 at 15.25.30.png` (binary.png, 616.8 KB) - Binary asset (image/documentation support).
- `docs/assets/screenshots/gan_2/Screenshot 2026-04-10 at 15.25.33.png` (binary.png, 523.4 KB) - Binary asset (image/documentation support).

### `docs/literature`

- `docs/literature/2025-11_PENTRE_Michelin_Bibops.pdf` (binary.pdf, 49.6 KB) - Binary asset (image/documentation support).
- `docs/literature/2512.14982v1.pdf` (binary.pdf, 1766.7 KB) - Binary asset (image/documentation support).
- `docs/literature/A05 Injection - OWASP Top 10:2025.pdf` (binary.pdf, 102.4 KB) - Binary asset (image/documentation support).
- `docs/literature/Knowledge graph - Wikipedia.pdf` (binary.pdf, 434.8 KB) - Binary asset (image/documentation support).
- `docs/literature/docu_widad.pdf` (binary.pdf, 111.0 KB) - Binary asset (image/documentation support).

### `docs/notebooks`

- `docs/notebooks/analyse_d_AGENT_ia.ipynb` (notebook, 72.6 KB, 1528 lines) - Jupyter notebook (46 cells). First markdown: # Analyse des agents IA :
- `docs/notebooks/doc_Akram.ipynb` (notebook, 140.1 KB, 515 lines) - Jupyter notebook (8 cells). First markdown: # Observabilité
- `docs/notebooks/lang_chatbot/lang-agent.py` (python, 4.0 KB, 88 lines) - lang-agent.py — A LangChain agent with a RAG tool and model fallback. [functions=pycharm_docs_search]
- `docs/notebooks/lang_chatbot/lang-gen.py` (python, 4.1 KB, 83 lines) - lang-gen.py — A LangChain agent that drafts a Python release newsletter. [functions=run_newsletter]
- `docs/notebooks/lang_chatbot/main.py` (python, 4.9 KB, 120 lines) - Welcome student! Today we're building a RAG (Retrieval-Augmented Generation) pipeline. [functions=format_history]
- `docs/notebooks/lang_chatbot/tools.py` (python, 5.2 KB, 127 lines) - tools.py — LangChain tools used by lang-gen.py. [functions=_fetch, _find_latest_url, _extract_highlights, fetch_python_whatsnew]

### `docs/operations`

- `docs/operations/RUNNERS.md` (documentation, 0.6 KB, 26 lines) - New Script Runners

### `docs/presentations`

- `docs/presentations/PRESENTATION_RACING.md` (documentation, 18.2 KB, 323 lines) - BibOps Racing Arena — Script du Présentateur
- `docs/presentations/slides.pdf` (binary.pdf, 60.6 KB) - Binary asset (image/documentation support).

### `logs`

- `logs/arena/hub.log` (text, 78.7 KB, 1356 lines) - INFO:     Started server process [30267]
- `logs/arena/team_Ferrari_Pro.log` (text, 21.4 KB, 287 lines) - [94m[1m══════════════════════════════════════════════════════════════[0m
- `logs/arena/team_McLaren_New.log` (text, 22.5 KB, 297 lines) - [94m[1m══════════════════════════════════════════════════════════════[0m
- `logs/arena/team_McLaren_Ollama.log` (text, 13.5 KB, 210 lines) - [92m[1m══════════════════════════════════════════════════════════════[0m
- `logs/arena/team_RedBull_Fast.log` (text, 22.5 KB, 295 lines) - [93m[1m══════════════════════════════════════════════════════════════[0m
- `logs/arena/team_RedBull_GPT.log` (text, 13.4 KB, 213 lines) - [92m[1m══════════════════════════════════════════════════════════════[0m
- `logs/arena/team_Scuderia_Claude.log` (text, 13.4 KB, 208 lines) - [96m[1m══════════════════════════════════════════════════════════════[0m

### `pyproject.toml`

- `pyproject.toml` (config/script, 0.2 KB, 11 lines) - [project]

### `requirements.txt`

- `requirements.txt` (documentation, 0.1 KB, 12 lines) - chromadb

### `scripts/benchmark`

- `scripts/benchmark/compare_architectures.py` (python, 21.9 KB, 617 lines) - Compare "LLM Unique" (zero-shot) vs "Systeme Multi-Agents" on one CSV. [classes=ArchMetrics | functions=_resolve_input_csv, _count_tokens_fallback, _extract_ollama_text, _extract_ollama_token_usage] | imports: `src/bibops/evaluation/composite_policy.py`, `src/bibops/evaluation/evaluator_registry.py`, `src/bibops/evaluation/greenops.py`, `src/bibops/evaluation/llm_judge.py`, `src/bibops/evaluation/quality_evaluator.py` (+4 more)
- `scripts/benchmark/run_core.py` (python, 0.1 KB, 7 lines) - Run the core benchmark (wrapper script). | imports: `src/bibops/benchmark/core.py`
- `scripts/benchmark/run_mcp_tools.py` (python, 0.2 KB, 9 lines) - Run the MCP tools benchmark (wrapper script). | imports: `src/bibops/benchmark/mcp_tools.py`
- `scripts/benchmark/run_pipeline.py` (python, 0.2 KB, 7 lines) - Run the full agent pipeline benchmark (wrapper script). | imports: `src/bibops/benchmark/pipeline.py`
- `scripts/benchmark/validate_benchmark_output.py` (python, 5.9 KB, 145 lines) - Validate benchmark output schema and critical fields. [functions=_expect, _validate_arch_metrics, validate_payload, main]

### `scripts/copilot`

- `scripts/copilot/run_agent_mcp.py` (python, 0.2 KB, 9 lines) - Run Copilot + MCP multi-model benchmark. | imports: `src/bibops/evaluation/agent_copilot_mcp.py`
- `scripts/copilot/test_api.py` (python, 0.3 KB, 10 lines) - Run Copilot API smoke test. | imports: `src/test_copilot_api.py`

### `scripts/dev`

- `scripts/dev/build_it_vector_db.py` (python, 0.2 KB, 7 lines) - Initialize BibOps IT support vector database. | imports: `src/bibops/it_support/memoire_RAG.py`
- `scripts/dev/init_sqlite.py` (python, 0.2 KB, 7 lines) - Initialize BibOps SQLite database. | imports: `src/bibops/it_support/baseSQL.py`
- `scripts/dev/reorganize_repo.sh` (config/script, 8.5 KB, 149 lines) - #!/usr/bin/env bash
- `scripts/dev/run_mcp_server.py` (python, 0.1 KB, 7 lines) - Run BibOps MCP server. | imports: `src/bibops/it_support/serveur_mcp.py`

### `scripts/racing`

- `scripts/racing/run_arena.py` (python, 0.1 KB, 7 lines) - Run the distributed racing arena. | imports: `src/bibops/racing/start_arena.py`
- `scripts/racing/run_demo.py` (python, 0.1 KB, 7 lines) - Run the standalone racing demo. | imports: `src/bibops/racing/demo.py`
- `scripts/racing/run_hub.py` (python, 0.2 KB, 13 lines) - Run the racing hub server.

### `src/__init__.py`

- `src/__init__.py` (python, 0.0 KB, 0 lines) - Package initializer.

### `src/bibops/__init__.py`

- `src/bibops/__init__.py` (python, 0.2 KB, 9 lines) - BibOps reorganized package surface (non-destructive).

### `src/bibops/benchmark`

- `src/bibops/benchmark/__init__.py` (python, 0.0 KB, 0 lines) - Package initializer.
- `src/bibops/benchmark/ab_test_llm.py` (python, 21.7 KB, 646 lines) - Test A/B automatique : compare deux modeles via la Copilot API (proxy local). [functions=charger_copilot_api_key, _extraire_texte, _executer_avec_timeout, appeler_modele]
- `src/bibops/benchmark/ab_test_user.py` (python, 5.6 KB, 168 lines) - Test A/B humain : compare deux modeles Copilot API en aveugle. [functions=charger_copilot_api_key, _extraire_texte, appeler_modele, main]
- `src/bibops/benchmark/core.py` (python, 6.8 KB, 192 lines) - Python module. [functions=demander_feedback_utilisateur, _lire_champ, extraire_texte_reponse, extraire_compteurs_tokens]
- `src/bibops/benchmark/mcp_tools.py` (python, 7.8 KB, 256 lines) - Benchmark des outils MCP via le protocole MCP sur stdio. [functions=connecter_et_lister_outils, appeler_outil, benchmark_outils, sauvegarder_benchmark] | imports: `src/bibops/evaluation/evaluation.py`
- `src/bibops/benchmark/pipeline.py` (python, 2.2 KB, 63 lines) - Python module. [functions=run_benchmark_agent] | imports: `src/bibops/it_support/maestro.py`, `src/bibops/it_support/outils.py`
- `src/bibops/benchmark/test-biais-position.py` (python, 6.8 KB, 212 lines) - Test de biais de position avec juge LLM. [functions=_binom_pmf, binom_test_two_sided, main] | imports: `src/bibops/benchmark/__init__.py`, `src/bibops/benchmark/ab_test_llm.py`

### `src/bibops/common`

- `src/bibops/common/__init__.py` (python, 0.2 KB, 5 lines) - Shared helpers for the reorganized BibOps layout. | imports: `src/bibops/common/paths.py`
- `src/bibops/common/paths.py` (python, 0.3 KB, 9 lines) - Centralized project paths for the new package layout.

### `src/bibops/evaluation`

- `src/bibops/evaluation/__init__.py` (python, 0.0 KB, 0 lines) - Package initializer.
- `src/bibops/evaluation/adversarial.py` (python, 18.0 KB, 440 lines) - src/bibops/evaluation/adversarial_loop.py [classes=IterationResult, AdversarialReport | functions=_banner, _header, _wrap, _metric_bar] | imports: `src/bibops/evaluation/discriminator.py`, `src/bibops/it_support/maestro.py`, `src/bibops/it_support/outils.py`
- `src/bibops/evaluation/adversarial_loop.py` (python, 0.1 KB, 3 lines) - Compatibility alias for legacy module name. | imports: `src/bibops/evaluation/adversarial.py`
- `src/bibops/evaluation/agent_copilot_mcp.py` (python, 0.1 KB, 3 lines) - Compatibility alias for legacy module name. | imports: `src/bibops/evaluation/copilot_mcp.py`
- `src/bibops/evaluation/agent_langchain_mcp.py` (python, 0.1 KB, 3 lines) - Compatibility alias for legacy module name. | imports: `src/bibops/evaluation/langchain_mcp.py`
- `src/bibops/evaluation/composite_policy.py` (python, 7.6 KB, 178 lines) - Composite scoring and release decision policy for benchmark outputs. [classes=CompositePolicy | functions=_clamp01, _safe_float, _inverse_minmax]
- `src/bibops/evaluation/config_evaluation.py` (python, 1.7 KB, 57 lines) - Configuration de la formule d'évaluation des réponses des modèles LLM
- `src/bibops/evaluation/copilot_mcp.py` (python, 13.0 KB, 395 lines) - Agent Copilot + MCP [functions=_copilot_headers, traduire_outils_mcp_vers_openai, traiter_ticket, benchmark] | imports: `src/bibops/evaluation/evaluation.py`
- `src/bibops/evaluation/discriminator.py` (python, 9.6 KB, 233 lines) - src/bibops/evaluation/discriminator.py [classes=DiscriminatorOutput, DiscriminatorLLM | functions=_extract_usage]
- `src/bibops/evaluation/evaluation.py` (python, 0.1 KB, 3 lines) - Compatibility alias for legacy module name. | imports: `src/bibops/evaluation/llm_judge.py`
- `src/bibops/evaluation/evaluator_registry.py` (python, 1.5 KB, 42 lines) - Registry for pluggable benchmark evaluators. [classes=Evaluator, EvaluatorRegistry]
- `src/bibops/evaluation/greenops.py` (python, 1.1 KB, 42 lines) - GreenOps utilities for token-based carbon estimation. [functions=calculate_carbon_footprint]
- `src/bibops/evaluation/langchain_mcp.py` (python, 10.1 KB, 323 lines) - Agent Copilot + MCP — Version LangGraph [functions=creer_schema_pydantic, creer_outil_langchain, recuperer_outils_langchain, creer_agent] | imports: `src/bibops/evaluation/evaluation.py`
- `src/bibops/evaluation/llm_judge.py` (python, 27.6 KB, 687 lines) - src/bibops/evaluation/evaluation.py [classes=EvaluationResult, LLMProfessor, EvaluationEngine | functions=filter_by_model, compare_models] | imports: `src/bibops/evaluation/config_evaluation.py`, `src/bibops/evaluation/rca_engine.py`
- `src/bibops/evaluation/local_kaggle_exam.json` (data-json, 7.1 KB, 71 lines) - JSON object keys: examName, version, source, questions
- `src/bibops/evaluation/quality_evaluator.py` (python, 1.7 KB, 56 lines) - Quality evaluator wrapper around BibOps LLM judge. [classes=QualityEvaluator] | imports: `src/bibops/evaluation/llm_judge.py`
- `src/bibops/evaluation/rca.py` (python, 1.9 KB, 51 lines) - Python module. [classes=RCAEngine]
- `src/bibops/evaluation/rca_engine.py` (python, 0.1 KB, 5 lines) - Compatibility alias for legacy module name. | imports: `src/bibops/evaluation/rca.py`
- `src/bibops/evaluation/result_schema.py` (python, 0.8 KB, 30 lines) - Shared schema helpers for benchmark output payloads. [functions=build_benchmark_payload]
- `src/bibops/evaluation/rule_engine.py` (python, 0.3 KB, 10 lines) - Rule-based evaluation wrappers. | imports: `src/bibops/evaluation/evaluation.py`
- `src/bibops/evaluation/run_kaggle_exam.py` (python, 16.8 KB, 515 lines) - Kaggle Standardized Agent Exam (SAE) runner for BibOps Maestro. [functions=_banner, _safe_json, _read_secret, _write_secret] | imports: `src/bibops/it_support/agent.py`, `src/bibops/it_support/tools.py`
- `src/bibops/evaluation/run_local_kaggle_exam.py` (python, 6.2 KB, 178 lines) - Executable runner script. [functions=clean_text, normalize_answer, call_judge, main] | imports: `src/bibops/it_support/agent.py`, `src/bibops/it_support/tools.py`
- `src/bibops/evaluation/security_llminspector_adapter.py` (python, 11.1 KB, 291 lines) - LLMInspector-inspired security evaluator adapter for BibOps. [classes=_RiskPack, SecurityLLMInspectorAdapter | functions=_clamp, _contains_any, _extract_urls] | imports: `src/bibops/evaluation/security_profile.py`
- `src/bibops/evaluation/security_profile.py` (python, 2.3 KB, 100 lines) - Security profiles and constants for BibOps evaluation. [classes=SecurityProfile]

### `src/bibops/it_support`

- `src/bibops/it_support/__init__.py` (python, 0.7 KB, 24 lines) - Public API for BibOps IT support domain. | imports: `src/bibops/it_support/agent.py`, `src/bibops/it_support/database.py`, `src/bibops/it_support/memory.py`, `src/bibops/it_support/rag.py`, `src/bibops/it_support/tools.py`
- `src/bibops/it_support/agent.py` (python, 18.7 KB, 529 lines) - Python module. [classes=ToolCallTrace, LLMTurnTrace, MaestroRunTrace | functions=_now_utc_iso, _preview, _extract_action, _routing_hint] | imports: `src/bibops/it_support/memoire_courte.py`, `src/bibops/it_support/outils.py`
- `src/bibops/it_support/baseSQL.py` (python, 0.2 KB, 5 lines) - Compatibility alias for legacy module name. | imports: `src/bibops/it_support/database.py`
- `src/bibops/it_support/database.py` (python, 2.4 KB, 50 lines) - Python module. [functions=initialiser_base_de_donnees]
- `src/bibops/it_support/maestro.py` (python, 0.2 KB, 5 lines) - Compatibility alias for legacy module name. | imports: `src/bibops/it_support/agent.py`
- `src/bibops/it_support/mcp_server.py` (python, 1.0 KB, 29 lines) - Python module. [functions=mcp_verifier_statut_serveur, mcp_chercher_documentation_technique, mcp_chercher_dans_kb] | imports: `src/bibops/it_support/outils.py`
- `src/bibops/it_support/memoire_RAG.py` (python, 0.2 KB, 5 lines) - Compatibility alias for legacy module name. | imports: `src/bibops/it_support/rag.py`
- `src/bibops/it_support/memoire_courte.py` (python, 0.1 KB, 5 lines) - Compatibility alias for legacy module name. | imports: `src/bibops/it_support/memory.py`
- `src/bibops/it_support/memory.py` (python, 0.6 KB, 14 lines) - Python module. [classes=MemoCourTerme]
- `src/bibops/it_support/outils.py` (python, 1.1 KB, 37 lines) - Compatibility layer preserving legacy patch points for tests and callers. [functions=verifier_statut_serveur, chercher_dans_kb, chercher_documentation_technique] | imports: `src/bibops/it_support/__init__.py`, `src/bibops/it_support/tools.py`
- `src/bibops/it_support/rag.py` (python, 2.1 KB, 60 lines) - Python module. [functions=initialiser_documentation]
- `src/bibops/it_support/serveur_mcp.py` (python, 0.1 KB, 5 lines) - Compatibility alias for legacy module name. | imports: `src/bibops/it_support/mcp_server.py`
- `src/bibops/it_support/tools.py` (python, 10.6 KB, 300 lines) - Python module. [classes=ToolPolicy | functions= get_tool_policy, get_tool_policies]

### `src/bibops/racing`

- `src/bibops/racing/__init__.py` (python, 0.1 KB, 4 lines) - src/bibops/racing — Système Multi-Agents de Stratégie Course (F1/WEC)
- `src/bibops/racing/demo.py` (python, 7.0 KB, 205 lines) - Racing MAS — Demo Script [functions=print_banner, print_telemetry, print_step_header, print_agent_message] | imports: `src/bibops/racing/graph.py`, `src/bibops/racing/state.py`
- `src/bibops/racing/experts.py` (python, 5.8 KB, 150 lines) - Racing MAS — Expert Nodes [functions=_get_llm, tire_engineer_node, fuel_engineer_node, race_engineer_node]
- `src/bibops/racing/graph.py` (python, 2.8 KB, 82 lines) - Racing MAS — LangGraph Assembly [functions=_route_from_supervisor, build_graph] | imports: `src/bibops/racing/experts.py`, `src/bibops/racing/state.py`, `src/bibops/racing/supervisor.py`
- `src/bibops/racing/hub/__init__.py` (python, 0.1 KB, 4 lines) - src/bibops/racing/hub — The Hub
- `src/bibops/racing/hub/ingest.py` (python, 6.0 KB, 181 lines) - Racing Hub — Ingestion RAG [functions=_load_all_documents, ingest]
- `src/bibops/racing/hub/ingest_racing.py` (python, 0.1 KB, 3 lines) - Compatibility alias for legacy module name. | imports: `src/bibops/racing/hub/ingest.py`
- `src/bibops/racing/hub/race_engine.py` (python, 9.8 KB, 264 lines) - Racing Hub — Race Engine [classes=RaceState, RaceEngine]
- `src/bibops/racing/hub/rag_service.py` (python, 3.9 KB, 106 lines) - Racing Hub — RAG Service [classes=RacingRAG]
- `src/bibops/racing/hub/server.py` (python, 6.8 KB, 204 lines) - Racing Hub — FastAPI Server [classes=TeamDecision, AskMichelinRequest | functions=stream_telemetry, receive_decision, ask_michelin, get_status] | imports: `src/bibops/racing/hub/race_engine.py`, `src/bibops/racing/hub/rag_service.py`
- `src/bibops/racing/start_arena.py` (python, 6.4 KB, 177 lines) - BibOps Racing — Arena Launcher [functions=_banner, _ensure_log_dir, _log_path, _open_log]
- `src/bibops/racing/state.py` (python, 1.7 KB, 48 lines) - Racing MAS — Shared State [classes=RacingState]
- `src/bibops/racing/supervisor.py` (python, 6.2 KB, 159 lines) - Racing MAS — Supervisor Node [classes=RoutingDecision | functions=_get_llm, _experts_already_consulted, _format_expert_reports, supervisor_node] | imports: `src/bibops/racing/state.py`
- `src/bibops/racing/team_client/__init__.py` (python, 0.1 KB, 4 lines) - src/bibops/racing/team_client — Écurie IA
- `src/bibops/racing/team_client/graph.py` (python, 2.6 KB, 80 lines) - Team Client — LangGraph Assembly [functions=_route_from_principal, build_graph] | imports: `src/bibops/racing/team_client/nodes.py`, `src/bibops/racing/team_client/state_tools.py`
- `src/bibops/racing/team_client/main.py` (python, 8.0 KB, 228 lines) - Team Client — Main Listener [functions=_parse_args, _pfx, _banner, _log_lap] | imports: `src/bibops/racing/team_client/graph.py`, `src/bibops/racing/team_client/nodes.py`, `src/bibops/racing/team_client/state_tools.py`
- `src/bibops/racing/team_client/nodes.py` (python, 11.3 KB, 290 lines) - Team Client — LangGraph Nodes [classes=RoutingDecision, FinalDecision | functions=_get_llm, _experts_consulted, _execute_tool_calls, tire_expert_node] | imports: `src/bibops/racing/team_client/state_tools.py`
- `src/bibops/racing/team_client/state_tools.py` (python, 2.3 KB, 67 lines) - Team Client — State & Tools [classes=TeamState | functions=ask_michelin_engineer]

### `src/test_copilot_api.py`

- `src/test_copilot_api.py` (python, 3.5 KB, 131 lines) - Test de la Copilot API avec plusieurs LLMs sur des tickets IT. [functions=tester_modele]

### `tests`

- `tests/__init__.py` (python, 0.0 KB, 0 lines) - Package initializer.
- `tests/test_maestro.py` (python, 8.2 KB, 189 lines) - tests/test_maestro.py [classes=TestMaestroReActLoop | functions=make_fake_ollama_chat, _make_tool_mock] | imports: `src/bibops/it_support/maestro.py`
- `tests/test_memoire.py` (python, 3.7 KB, 86 lines) - tests/test_memoire.py [classes=TestMemoCourTerme] | imports: `src/bibops/it_support/memoire_courte.py`
- `tests/test_outils.py` (python, 8.9 KB, 195 lines) - tests/test_outils.py [classes=TestVerifierStatutServeur, TestChercherDansKB, TestChercherDocumentationTechnique | functions=_sqlite_mock] | imports: `src/bibops/it_support/outils.py`

## 7) Untracked Files (attention before commit)

- `LLMInspector-main/.gitignore`
- `LLMInspector-main/.gitlab-ci.yml`
- `LLMInspector-main/.pre-commit-config.yaml`
- `LLMInspector-main/.streamlit/config.toml`
- `LLMInspector-main/LICENSE`
- `LLMInspector-main/LLMInspector_main.py`
- `LLMInspector-main/README.md`
- `LLMInspector-main/ci_badges.sh`
- `LLMInspector-main/config.ini`
- `LLMInspector-main/docs/Makefile`
- `LLMInspector-main/docs/README.md`
- `LLMInspector-main/docs/api.rst`
- `LLMInspector-main/docs/assets/images/README.md`
- `LLMInspector-main/docs/assets/images/llminspector_flow_v1.0.png`
- `LLMInspector-main/docs/conf.py`
- `LLMInspector-main/docs/index.rst`
- `LLMInspector-main/docs/llminspector_flow_v1.0.png`
- `LLMInspector-main/docs/make.bat`
- `LLMInspector-main/example/Data/AdversarialAttack_Data.xlsx`
- `LLMInspector-main/example/Data/GenAI_tool_-_Qualitative_Evaluation_V1.0.xlsx`
- `LLMInspector-main/example/Data/Golden_data_sample.xlsx`
- `LLMInspector-main/example/Data/LLMInspector_Risk_assessment_V1.0.xlsx`
- `LLMInspector-main/example/Tutorials/adversarial_example.ipynb`
- `LLMInspector-main/example/Tutorials/alignment_example.ipynb`
- `LLMInspector-main/example/Tutorials/evaluate_example.ipynb`
- `LLMInspector-main/example/Tutorials/rag_example.ipynb`
- `LLMInspector-main/images/LLM Evaluation.png`
- `LLMInspector-main/images/Michelin_logo_image.png`
- `LLMInspector-main/images/images-logo2 1.png`
- `LLMInspector-main/images/llminspector_flow_v1.0.jpg`
- `LLMInspector-main/images/white_logo-removebg-preview 1.png`
- `LLMInspector-main/llm_inspector/__init__.py`
- `LLMInspector-main/llm_inspector/adversarial.py`
- `LLMInspector-main/llm_inspector/alignment.py`
- `LLMInspector-main/llm_inspector/alignment_replace_function.py`
- `LLMInspector-main/llm_inspector/constants.py`
- `LLMInspector-main/llm_inspector/eval_metrics.py`
- `LLMInspector-main/llm_inspector/llminspector.py`
- `LLMInspector-main/llm_inspector/rag_eval.py`
- `LLMInspector-main/pages/Documents_links.py`
- `LLMInspector-main/pages/Metric_Evaluation.py`
- `LLMInspector-main/pages/RAG_data_generation.py`
- `LLMInspector-main/pages/adverserial_data_generation.py`
- `LLMInspector-main/pages/alignment_data_generation.py`
- `LLMInspector-main/pages/welcome_home.py`
- `LLMInspector-main/pyproject.toml`
- `LLMInspector-main/req.txt`
- `LLMInspector-main/setup.py`
- `LLMInspector-main/sonar-project.properties`
- `LLMInspector-main/tests/__init__.py`
- `LLMInspector-main/tests/test_adversarial.py`
- `LLMInspector-main/tests/test_alignment.py`
- `LLMInspector-main/tests/test_evaluate.py`
- `LLMInspector-main/tests/test_rag.py`
- `LLMInspector-main/tests/test_sample/test_adversarialdata.xlsx`
- `LLMInspector-main/tests/test_sample/test_alignmentdata.xlsx`
- `LLMInspector-main/tests/test_sample/test_config.ini`
- `data/outputs/benchmark/comparison_results.json`
- `docs/LLMINSPECTOR_GAP_ANALYSIS.md`
- `scripts/benchmark/compare_architectures.py`
- `scripts/benchmark/validate_benchmark_output.py`
- `scripts/dev/reorganize_repo.sh`
- `src/bibops/evaluation/adversarial_loop.py`
- `src/bibops/evaluation/agent_copilot_mcp.py`
- `src/bibops/evaluation/agent_langchain_mcp.py`
- `src/bibops/evaluation/composite_policy.py`
- `src/bibops/evaluation/evaluation.py`
- `src/bibops/evaluation/evaluator_registry.py`
- `src/bibops/evaluation/greenops.py`
- `src/bibops/evaluation/local_kaggle_exam.json`
- `src/bibops/evaluation/quality_evaluator.py`
- `src/bibops/evaluation/rca_engine.py`
- `src/bibops/evaluation/result_schema.py`
- `src/bibops/evaluation/run_kaggle_exam.py`
- `src/bibops/evaluation/run_local_kaggle_exam.py`
- `src/bibops/evaluation/security_llminspector_adapter.py`
- `src/bibops/evaluation/security_profile.py`
- `src/bibops/it_support/baseSQL.py`
- `src/bibops/it_support/maestro.py`
- `src/bibops/it_support/memoire_RAG.py`
- `src/bibops/it_support/memoire_courte.py`
- `src/bibops/it_support/outils.py`
- `src/bibops/it_support/serveur_mcp.py`
- `src/bibops/racing/hub/ingest_racing.py`

## 8) Notes for Maintaining Clarity

- Keep executable entrypoints in `scripts/` and reusable logic in `src/bibops/`.
- Keep evaluation outputs in `data/outputs/` and temporary files in `data/temp/`.
- Keep large binaries/databases out of code review focus; document provenance in Markdown.
- If legacy namespaces reappear (`src/agents*`, `src/llm_professor`), redirect to `src/bibops/*`.
