"""Run the full agent pipeline benchmark (wrapper script)."""

from src.bibops.benchmark.pipeline import run_benchmark_agent


if __name__ == "__main__":
    run_benchmark_agent(model_name="phi3:latest")
