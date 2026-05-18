"""Tests for the enriched JSON shape persisted by the adversarial benchmark.

The page at docs/index.html needs the full conversation per iteration, not just
scores. This test pins the contract _summarize_report() exposes.
"""
from src.bibops.benchmark.adversarial import AdversarialReport, IterationResult
from src.bibops.benchmark.adversarial_convergence import _summarize_report


def _make_iteration(
    numero: int,
    sf: int,
    sr: int,
    sc: int,
    reponse: str,
    feedback: str = "",
    tool_calls=None,
) -> IterationResult:
    return IterationResult(
        numero=numero,
        reponse_agent=reponse,
        score_faithfulness=sf,
        score_relevance=sr,
        score_context=sc,
        is_perfect=(sf + sr + sc) / 3 >= 7,
        feedback=feedback,
        tool_calls=tool_calls or [],
    )


def test_summarize_report_carries_ticket_and_rca_at_top_level():
    rep = AdversarialReport(
        ticket="Mon VPN Cisco renvoie l'erreur 412 depuis la Chine.",
        rca_ground_truth="Blocage du port UDP 1194 par le GFW; fallback TCP 443.",
        iterations=[_make_iteration(1, 8, 8, 8, "Reponse OK")],
        succes=True,
        iterations_necessaires=1,
    )

    out = _summarize_report(rep, "VPN-001")

    assert out["ticket_text"] == rep.ticket
    assert out["rca_ground_truth"] == rep.rca_ground_truth


def test_summarize_report_persists_response_text_per_iteration():
    rep = AdversarialReport(
        ticket="t", rca_ground_truth="r",
        iterations=[
            _make_iteration(1, 3, 5, 4, "Reponse iter 1 incomplete."),
            _make_iteration(2, 8, 9, 8, "Reponse iter 2 complete avec TCP 443."),
        ],
    )

    out = _summarize_report(rep, "T-1")

    assert out["scores_par_iteration"][0]["reponse_agent"] == "Reponse iter 1 incomplete."
    assert out["scores_par_iteration"][1]["reponse_agent"] == "Reponse iter 2 complete avec TCP 443."


def test_summarize_report_persists_feedback_per_iteration():
    rep = AdversarialReport(
        ticket="t", rca_ground_truth="r",
        iterations=[_make_iteration(1, 3, 5, 4, "r1", feedback="Creuse la cause racine.")],
    )

    out = _summarize_report(rep, "T-1")

    assert out["scores_par_iteration"][0]["feedback"] == "Creuse la cause racine."


def test_summarize_report_persists_tool_calls_for_react():
    tool_calls = [
        {"tool": "chercher_documentation_technique", "argument": "VPN Chine 412", "ok": True},
        {"tool": "verifier_statut_serveur", "argument": "vpn", "ok": True},
    ]
    rep = AdversarialReport(
        ticket="t", rca_ground_truth="r",
        iterations=[_make_iteration(1, 8, 8, 8, "r", tool_calls=tool_calls)],
    )

    out = _summarize_report(rep, "T-1")

    assert out["scores_par_iteration"][0]["tool_calls"] == tool_calls


def test_summarize_report_empty_tool_calls_for_zero_shot():
    rep = AdversarialReport(
        ticket="t", rca_ground_truth="r",
        iterations=[_make_iteration(1, 8, 8, 8, "r", tool_calls=[])],
    )

    out = _summarize_report(rep, "T-1")

    assert out["scores_par_iteration"][0]["tool_calls"] == []


def test_summarize_report_truncates_long_response_to_800_chars():
    long_text = "x" * 2000
    rep = AdversarialReport(
        ticket="t", rca_ground_truth="r",
        iterations=[_make_iteration(1, 8, 8, 8, long_text)],
    )

    out = _summarize_report(rep, "T-1")

    assert len(out["scores_par_iteration"][0]["reponse_agent"]) <= 803
    assert out["scores_par_iteration"][0]["reponse_agent"].endswith("...")
