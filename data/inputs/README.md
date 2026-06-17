# data/inputs

Version-controlled source inputs for benchmarks and evaluation.

- `benchmark/` — ticket scenarios (`tickets_scenario_1.csv`), the A2A probe suite, the local Kaggle exam, and A/B statement sets.
- `probes/` — categorised probe JSON consumed by the integration suites (`bibops eval suite`) and the adversarial loop, organised by category: `security/`, `quality/`, `robustness/`, `tool_use/`. Override the directory with `BIBOPS_PROBES_DIR`.

The knowledge base used for RAG lives separately under `data/kb/`.
