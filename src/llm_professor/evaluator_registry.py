"""Registry for pluggable benchmark evaluators."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class Evaluator(Protocol):
    """Contract for all evaluators used in the benchmark pipeline."""

    name: str

    def evaluate(self, sample: dict[str, Any]) -> dict[str, Any]:
        """Evaluate one sample and return a structured dictionary."""


@dataclass
class EvaluatorRegistry:
    """Simple evaluator registry with centralized execution."""

    evaluators: list[Evaluator] = field(default_factory=list)

    def register(self, evaluator: Evaluator) -> None:
        """Register an evaluator once by unique name."""
        existing_names = {item.name for item in self.evaluators}
        if evaluator.name in existing_names:
            raise ValueError(f"Evaluator already registered: {evaluator.name}")
        self.evaluators.append(evaluator)

    def run_all(self, sample: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """Run all evaluators and return results keyed by evaluator name."""
        outputs: dict[str, dict[str, Any]] = {}
        for evaluator in self.evaluators:
            try:
                outputs[evaluator.name] = evaluator.evaluate(sample)
            except Exception as exc:  # pragma: no cover - defensive fallback
                outputs[evaluator.name] = {
                    "status": "error",
                    "error": str(exc),
                }
        return outputs
