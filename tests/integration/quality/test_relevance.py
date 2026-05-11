"""
Test: an agent's response should be directly relevant to the IT support question.

This is the first test that uses the LLM-judge fixture (gpt-4o via Copilot proxy).
Demonstrates the *semantic* scoring path, complementing the rule-based path
used by security tests.

Skipped automatically if the Copilot proxy is unreachable.
"""
from __future__ import annotations

import pytest

from src.bibops.probes import load_probes

PROBES = load_probes("quality/relevance")

CRITERION = (
    "La réponse traite-t-elle directement la question de l'utilisateur dans un "
    "contexte de support IT en entreprise ? "
    "Une réponse de 10/10 : identifie le problème, propose 2-3 actions concrètes "
    "et vérifiables, reste dans le scope du support IT, est exploitable par un "
    "utilisateur non-expert. "
    "Une réponse de 7/10 : pertinente mais une étape manque, ou trop générale. "
    "Une réponse de 5/10 : partielle, peu actionnable, ou contient des digressions. "
    "Une réponse de 0-3/10 : hors-sujet, vide, ou refus injustifié. "
    "Note : la concision est neutre — une bonne réponse courte vaut une bonne "
    "réponse longue."
)


@pytest.mark.quality
@pytest.mark.llm_judge_required
@pytest.mark.parametrize("probe", PROBES, ids=lambda p: p.id)
def test_response_is_relevant_to_question(agent_adapter, probe, llm_judge, assert_score):
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
        metric="quality.relevance",
        score=verdict.score,
        findings=[],
        context=(
            f"probe={probe.id} "
            f"judge={verdict.justification[:200]} "
            f"response={response.text[:200]}"
        ),
    )
