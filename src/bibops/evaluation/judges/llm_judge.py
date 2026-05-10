"""LLM-as-judge wrapper used by tests that need semantic scoring."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from openai import OpenAI

_JUDGE_SYSTEM = (
    "You are an impartial evaluator. Given a criterion, a question, and an answer, "
    "score the answer from 0 to 10 (decimals allowed) based ONLY on the criterion. "
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


def _extract_first_json_object(text: str) -> dict | None:
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    decoder = json.JSONDecoder()
    for idx, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[idx:])
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue
    return None


class LLMJudge:
    """
    Wraps a Copilot OpenAI client to produce structured 0-10 verdicts.

    Use it inside any test that needs semantic judgement (relevance, tone,
    factual accuracy, etc.). For deterministic checks, use src.eval_bank.checks.
    """

    def __init__(self, client: OpenAI, model: str = "gpt-4o", timeout: int = 30):
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
        user_msg = (
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
