# data/outputs

Generated artefacts from benchmarks and reports. Mostly regenerable; a few result JSONs are committed for the write-up.

- `benchmark/*.json` — benchmark results, e.g. `comparison_results.json` (`bench compare-archs`), `adversarial_convergence.json` (`bench adversarial`), `security_race_report.json` (`racing adversarial`).
- `benchmark/charts/` — PNG charts from `bibops report charts` (gitignored).
- `coverage.json` — coverage report consumed by `bibops dev coverage-gates`.

Safe to delete and regenerate.
