# BibOps Project Structure (Non-Destructive Reorganization)

This repository now has a new organization layer under `src/bibops` while keeping all existing code in place.

## Why this approach

- No existing code was deleted.
- Existing imports and entry points keep working.
- New code can progressively target `src/bibops/*`.

## New package surface

- `src/bibops/it_support`: wrappers for `src/agents/*`
- `src/bibops/racing`: wrappers for `src/agents_racing/*`
- `src/bibops/evaluation`: wrappers for `src/llm_professor/*`
- `src/bibops/benchmark`: wrappers for `src/benchmark/*`
- `src/bibops/common`: shared paths and future shared utilities

## New script entry points

- `scripts/dev/*`: setup/dev utilities
- `scripts/benchmark/*`: benchmark runners
- `scripts/racing/*`: racing hub/arena runners
- `scripts/copilot/*`: Copilot-related runners

## Data directories

- `data/raw`: source datasets and KB content
- `data/fixtures`: deterministic test data
- `data/runtime`: generated local runtime artifacts (sqlite/chroma/logs)
- `data/outputs`: generated benchmark outputs

Legacy paths are intentionally preserved for backward compatibility.
