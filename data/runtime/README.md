# data/runtime

Runtime-generated traces (gitignored — safe to delete and regenerate).

- `maestro/maestro_runs.jsonl` — one JSON record per `lancer_agent` run (`MaestroRunTrace`); appended, not rotated.

The SQLite database and Chroma vector store live under `data/databases/`, not here.
