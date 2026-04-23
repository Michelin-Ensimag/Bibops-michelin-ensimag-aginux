"""Quality evaluator wrapper around BibOps LLM judge."""

from __future__ import annotations

from typing import Any

from .llm_judge import LLMProfessor


class QualityEvaluator:
    """Adapter that exposes LLMProfessor scoring via evaluator contract."""

    name = "quality"

    def __init__(self, judge: LLMProfessor):
        self._judge = judge

    def evaluate(self, sample: dict[str, Any]) -> dict[str, Any]:
        """
        Score one response with the existing LLM judge.

        Expected sample keys:
            - ticket_text
            - answer_text
            - diagnostic_rca (optional)
        """
        ticket_text = str(sample.get("ticket_text") or "")
        answer_text = str(sample.get("answer_text") or "")
        diagnostic_rca = str(sample.get("diagnostic_rca") or "Non disponible")

        try:
            result = self._judge.chain.invoke(
                {
                    "ticket": ticket_text,
                    "reponse_agent": answer_text,
                    "diagnostic_rca": diagnostic_rca,
                    "format_instructions": self._judge.parser.get_format_instructions(),
                }
            )
            note = float(result.get("note", 0))
            note = max(0.0, min(10.0, note))
            justification = str(result.get("justification", ""))

            return {
                "status": "ok",
                "score": round(note, 2),
                "justification": justification,
                "error": "",
            }
        except Exception as exc:
            return {
                "status": "error",
                "score": 0.0,
                "justification": "",
                "error": f"judge_error: {exc}",
            }
