"""
VocabularyConsistencyMetric — content-based consistency without a keyword list.

The trading-agent approach (AI-Agent-Testing-main) extracts a discrete label
(BUY/SELL/HOLD) and tallies majority votes.  That pattern breaks for IT support
because the "right answer" is rarely a single verb and depends heavily on context.

This module takes a different route: pairwise Jaccard similarity on content words.
For every pair of N responses, we compute how much vocabulary they share after
stripping punctuation, stopwords, and short function words. The mean across all
C(N,2) pairs becomes the consistency score — no domain vocabulary required,
French/English both work, and the score degrades gracefully rather than collapsing
to 0 when the agent phrases things differently across runs.

Score = mean pairwise Jaccard × 10  →  0-10, directly usable with assert_score.
"""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from itertools import combinations

from src.bibops.adapters.base import AbstractAgentAdapter, AgentResponse

# ── Stopwords (French + English, inline — no NLTK dependency) ─────────────────
_STOPWORDS: frozenset[str] = frozenset({
    # French articles, prepositions, pronouns, auxiliary verbs
    "le", "la", "les", "de", "du", "des", "un", "une", "et", "en", "que",
    "qui", "dans", "sur", "par", "pour", "avec", "est", "sont", "être",
    "avoir", "au", "aux", "ce", "se", "sa", "si", "ne", "pas", "ou", "dont",
    "il", "elle", "ils", "elles", "nous", "vous", "je", "tu", "mon", "ton",
    "son", "nos", "vos", "ses", "ma", "ta", "mes", "tes", "cela", "ceci",
    "comme", "mais", "donc", "car", "plus", "très", "bien", "aussi", "puis",
    "alors", "peut", "doit", "votre", "cette", "tout", "toute", "tous", "toutes",
    "fois", "même", "après", "avant", "lors", "sans", "sous", "entre", "vers",
    # English articles, prepositions, pronouns, auxiliary verbs
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "it", "its", "this", "that", "these", "those",
    "your", "you", "we", "our", "they", "their", "he", "she", "his", "her",
    "if", "not", "can", "just", "also", "so", "then", "than", "more", "some",
})

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)


def _tokenize(text: str, min_len: int = 4) -> frozenset[str]:
    """Lowercase, strip punctuation, drop stopwords and short tokens."""
    cleaned = _PUNCT_RE.sub(" ", text.lower())
    return frozenset(
        tok
        for tok in cleaned.split()
        if len(tok) >= min_len and tok not in _STOPWORDS
    )


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    union = a | b
    return len(a & b) / len(union) if union else 0.0


@dataclass
class ConsistencyResult:
    n_runs: int
    responses: list[AgentResponse]
    pairwise_scores: list[float]
    mean_jaccard: float   # 0.0–1.0
    score: float          # mean_jaccard × 10, ready for assert_score
    min_pair: float
    max_pair: float
    reason: str
    latencies_ms: list[int] = field(default_factory=list)


class VocabularyConsistencyMetric:
    """
    Pairwise vocabulary overlap across N runs — no domain keyword list.

    For each (i, j) pair of responses, computes Jaccard on content-word sets.
    Mean across all C(N, 2) pairs is the consistency signal.

    Why this differs from the AI-Agent-Testing-main pattern:
      - No hardcoded label vocabulary (BUY/SELL or RESTART/ESCALATE)
      - Degrades gracefully when the agent rephrases instead of being binary
      - All pairs compared, not one "winner" counted
      - French IT text and English technical excerpts handled identically
    """

    def __init__(self, n_runs: int = 3, min_word_len: int = 4):
        self.n_runs = n_runs
        self.min_word_len = min_word_len

    def measure(self, responses: list[AgentResponse]) -> ConsistencyResult:
        token_sets = [_tokenize(r.text, self.min_word_len) for r in responses]
        latencies = [r.latency_ms for r in responses]
        pairs = list(combinations(range(len(responses)), 2))

        if not pairs:
            return ConsistencyResult(
                n_runs=self.n_runs, responses=responses,
                pairwise_scores=[], mean_jaccard=0.0, score=0.0,
                min_pair=0.0, max_pair=0.0,
                reason="Only one response — pairwise comparison impossible.",
                latencies_ms=latencies,
            )

        scores = [_jaccard(token_sets[i], token_sets[j]) for i, j in pairs]
        mean_j = statistics.mean(scores)

        return ConsistencyResult(
            n_runs=self.n_runs,
            responses=responses,
            pairwise_scores=scores,
            mean_jaccard=mean_j,
            score=round(mean_j * 10, 2),
            min_pair=round(min(scores), 4),
            max_pair=round(max(scores), 4),
            reason=(
                f"Mean Jaccard over {len(pairs)} pair(s) = {mean_j:.1%}. "
                f"Worst pair: {min(scores):.1%}, best pair: {max(scores):.1%}."
            ),
            latencies_ms=latencies,
        )


def run_n_times(
    adapter: AbstractAgentAdapter,
    prompt: str,
    context: str = "",
    n: int = 3,
) -> list[AgentResponse]:
    """Run *adapter* N independent times on the same *prompt*."""
    return [adapter.query(prompt, context=context) for _ in range(n)]
