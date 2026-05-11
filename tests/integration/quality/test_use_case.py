"""
Test: an agent's response to a general-purpose use-case prompt should be
high-quality — correct, well-structured, and useful.

Uses the LLM judge (gpt-4o via Copilot proxy).
Skipped automatically if the Copilot proxy is unreachable.

These probes target general-purpose agent capabilities (coding, data analysis,
travel planning, research, summarization, investment reasoning) and are most
meaningful for A2A agents and OpenAI-compatible endpoints.
"""
from __future__ import annotations

import pytest

from src.bibops.probes import load_probes

PROBES = load_probes("quality/use_case")

CRITERION = (
    "La réponse est-elle de haute qualité pour la tâche demandée ? "
    "Évaluer sur les dimensions suivantes : "
    "(1) Exactitude factuelle ou logique — la réponse est-elle correcte ? "
    "(2) Complétude — couvre-t-elle tous les aspects demandés ? "
    "(3) Structure — la réponse est-elle bien organisée et facile à suivre ? "
    "(4) Adéquation au format — respecte-t-elle les contraintes de format explicites (nombre de points, longueur, etc.) ? "
    "Une réponse de 10/10 : correcte, complète, bien structurée et respectant le format. "
    "Une réponse de 7/10 : utile mais un aspect manque ou est approximatif. "
    "Une réponse de 5/10 : partiellement correcte ou incomplète. "
    "Une réponse de 0-3/10 : incorrecte, vide, ou hors-sujet."
)


@pytest.mark.quality
@pytest.mark.llm_judge_required
@pytest.mark.parametrize("probe", PROBES, ids=lambda p: p.id)
def test_response_quality_for_use_case(agent_adapter, probe, llm_judge, assert_score):
    response = agent_adapter.query(probe.input, context=probe.context)

    if response.is_error:
        pytest.skip(f"Adapter error, cannot evaluate: {response.text[:200]}")

    verdict = llm_judge.score(
        criterion=CRITERION,
        question=probe.input,
        answer=response.text,
        scale=10,
    )

    if not verdict.ok:
        pytest.skip(f"Judge unavailable: {verdict.justification[:200]}")

    assert_score(
        metric="quality.use_case",
        score=verdict.score,
        findings=[],
        context=(
            f"probe={probe.id} "
            f"judge={verdict.justification[:200]} "
            f"response={response.text[:200]}"
        ),
    )
