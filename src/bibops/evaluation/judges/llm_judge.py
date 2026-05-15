"""LLM-as-judge wrapper used by tests that need semantic scoring."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from openai import OpenAI

from src.common.config import DEFAULT_JUDGE_MODEL
from src.common.text import extract_first_json as _extract_first_json_object

_JUDGE_SYSTEM = (
    "You are an impartial evaluator. Given a criterion, a question, and an answer, "
    "score the answer from 0 to 10 (decimals allowed) based ONLY on the criterion. "
    "Use the current evaluation date supplied in the user message when judging time-sensitive claims. "
    "Be strict but fair. Reply with strict JSON only, no prose, no code fences."
)


@dataclass
class JudgeVerdict:
    score: float
    justification: str
    raw: str = ""

    @property
    def ok(self) -> bool:
        return self.score >= 0 and not self.justification.startswith(("judge_error:", "judge_invalid_json:"))


class LLMJudge:
    """
    Wraps a Copilot OpenAI client to produce structured 0-10 verdicts.

    Use it inside any test that needs semantic judgement (relevance, tone,
    factual accuracy, etc.). For deterministic checks, use
    src.bibops.evaluation.checks.
    """

    def __init__(self, client: OpenAI, model: str = DEFAULT_JUDGE_MODEL, timeout: int = 30):
        self.client = client
        self.model = model
        self.timeout = timeout

    def score(
        self,
        *,
        criterion: str,
        question: str,
        answer: str,
        scale: int = 10,
    ) -> JudgeVerdict:
        current_date_utc = datetime.now(timezone.utc).date().isoformat()
        user_msg = (
            f"Current evaluation date (UTC): {current_date_utc}.\n"
            "Do not treat timestamps on this date as future-dated solely because your training data is older.\n\n"
            f"Criterion:\n{criterion}\n\n"
            f"Question:\n{question}\n\n"
            f"Answer:\n{answer}\n\n"
            f"Scale: 0 to {scale} (decimals allowed).\n"
            'Reply with JSON exactly: {"score": <number>, "justification": "<one or two sentences>"}'
        )
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": _JUDGE_SYSTEM},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0,
                timeout=self.timeout,
            )
            content = (resp.choices[0].message.content or "").strip()
            obj = _extract_first_json_object(content)
            if obj is None:
                return JudgeVerdict(
                    score=0.0,
                    justification=f"judge_invalid_json: {content[:200]}",
                    raw=content,
                )
            try:
                score = float(obj.get("score", 0.0))
            except (TypeError, ValueError):
                score = 0.0
            return JudgeVerdict(
                score=max(0.0, min(float(scale), score)),
                justification=str(obj.get("justification", "")),
                raw=content,
            )
        except Exception as exc:
            return JudgeVerdict(score=0.0, justification=f"judge_error: {exc}")
