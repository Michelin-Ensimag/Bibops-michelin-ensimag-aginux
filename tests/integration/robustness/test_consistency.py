"""
Consistency / determinism tests for the BibOps IT support agent.

Two metrics, both genuinely different from the AI-Agent-Testing-main approach:

  robustness.consistency   — pairwise vocabulary Jaccard across N runs
                             No keyword list; scores how much content-word overlap
                             exists between every pair of responses.
                             Works for French IT text without hardcoded action verbs.

  robustness.contradiction — LLM judge asked specifically "do any two responses
                             contradict each other?", not generic "are they coherent?".
                             Score 10 = all runs converge, 0 = direct contradiction found.

Usage:
    # Vocabulary metric only (Ollama, no Copilot proxy needed):
    PYTHONPATH=. pytest tests/integration/robustness/ -v -m "robustness and not llm_judge_required"

    # Both metrics (Ollama + Copilot proxy):
    PYTHONPATH=. pytest tests/integration/robustness/ -v -m robustness

    # Override number of runs:
    N_RUNS=5 PYTHONPATH=. pytest tests/integration/robustness/ -v
"""
from __future__ import annotations

import os

import pytest

from src.bibops.evaluation.metrics.consistency import VocabularyConsistencyMetric, run_n_times
from src.bibops.probes import load_probes

N_RUNS: int = int(os.environ.get("N_RUNS", "3"))

PROBES = load_probes("robustness/consistency")

# Sharper than "are they coherent?" — asks specifically whether recommendations
# are mutually exclusive or directly contradictory.
_CONTRADICTION_CRITERION = (
    "Tu reçois {n_runs} réponses d'un agent de support IT Michelin à exactement la même question.\n"
    "Ta seule mission : détecter si des réponses se contredisent DIRECTEMENT.\n\n"
    "Une CONTRADICTION directe signifie :\n"
    "- Une réponse recommande l'action X, une autre la déconseille explicitement.\n"
    "- Les diagnostics sont mutuellement exclusifs (ex : 'le problème vient du réseau' vs "
    "'le réseau n'est pas en cause, le problème est local').\n"
    "- Une réponse dit que la situation est anodine, une autre qu'elle est critique.\n\n"
    "Ce qui N'EST PAS une contradiction :\n"
    "- Deux formulations différentes pour la même idée.\n"
    "- Deux étapes valides présentées dans un ordre différent.\n"
    "- Une réponse plus détaillée qu'une autre.\n\n"
    "Score 10/10 : aucune contradiction — les réponses convergent.\n"
    "Score 5/10 : approches différentes mais compatibles.\n"
    "Score 0/10 : contradiction directe identifiée — citer les runs concernés.\n\n"
    "Réponds en JSON : {{\"score\": <0-10>, \"justification\": \"<une ou deux phrases>\"}}"
)


@pytest.mark.robustness
@pytest.mark.parametrize("probe", PROBES, ids=lambda p: p.id)
def test_vocabulary_consistency(agent_adapter, probe, assert_score):
    """
    Responses to the same question must share significant vocabulary.

    Scores pairwise Jaccard on content words across N runs.
    No keyword list — French IT text and English excerpts handled the same way.
    """
    metric = VocabularyConsistencyMetric(n_runs=N_RUNS)
    responses = run_n_times(agent_adapter, probe.input, context=probe.context, n=N_RUNS)

    errors = [r for r in responses if r.is_error]
    if len(errors) == N_RUNS:
        pytest.skip(
            f"All {N_RUNS} adapter calls failed — agent unreachable. "
            f"First error: {responses[0].text[:200]}"
        )

    result = metric.measure([r for r in responses if not r.is_error])

    assert_score(
        metric="robustness.consistency",
        score=result.score,
        findings=[result.reason],
        context=(
            f"probe={probe.id} "
            f"n_runs={N_RUNS} "
            f"pairwise={[round(s, 3) for s in result.pairwise_scores]} "
            f"errors={len(errors)}/{N_RUNS}"
        ),
    )


@pytest.mark.robustness
@pytest.mark.llm_judge_required
@pytest.mark.parametrize("probe", PROBES, ids=lambda p: p.id)
def test_no_contradiction_across_runs(agent_adapter, probe, llm_judge, assert_score):
    """
    No two runs should give mutually exclusive recommendations.

    The judge is asked specifically about contradictions — not generic coherence.
    This catches cases where the agent sometimes recommends restart and sometimes
    recommends escalation for the same deterministic scenario.
    """
    responses = run_n_times(agent_adapter, probe.input, context=probe.context, n=N_RUNS)

    errors = [r for r in responses if r.is_error]
    if len(errors) == N_RUNS:
        pytest.skip(
            f"All {N_RUNS} adapter calls failed — agent unreachable. "
            f"First error: {responses[0].text[:200]}"
        )

    separator = "\n\n" + "─" * 50 + "\n\n"
    combined = separator.join(
        f"[Run {i + 1}]\n{r.text}" for i, r in enumerate(responses)
    )

    verdict = llm_judge.score(
        criterion=_CONTRADICTION_CRITERION.format(n_runs=N_RUNS),
        question=probe.input,
        answer=combined,
        scale=10,
    )

    if not verdict.ok:
        pytest.skip(f"LLM judge unavailable: {verdict.justification[:200]}")

    assert_score(
        metric="robustness.contradiction",
        score=verdict.score,
        findings=[verdict.justification],
        context=(
            f"probe={probe.id} "
            f"n_runs={N_RUNS} "
            f"errors={len(errors)}/{N_RUNS}"
        ),
    )
