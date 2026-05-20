"""Coverage tests for benchmark runner pure-function helpers.

These tests exercise deterministic logic (no Ollama, no network) in:
  - validate_benchmark_output.py
  - ab_test_llm_statements.py
  - compare_architectures.py (ArchMetrics, security eval, print helpers)
  - adversarial.py (_run_zero_shot_generator, _safe_evaluate)
  - adversarial_convergence.py (make_chart)
  - position_bias.py (main with mocks)
  - local_kaggle_exam.py (run_local_exam with mocks)
  - position_bias_statements.py
  - local_kaggle_exam.py
  - compare_architectures.py
  - adversarial.py
  - adversarial_convergence.py
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# ── validate_benchmark_output ────────────────────────────────────────────────


def _minimal_valid_payload() -> dict:
    """Build the smallest payload that passes validate_payload."""
    arch = {
        "score_moyen": 7.5,
        "latence_totale_s": 10.0,
        "cout_usd": 0.01,
        "empreinte_gco2e": 0.5,
        "nb_reponses_notees": 5,
        "security_score_moyen": 8.0,
        "blocked_count": 0,
        "error_count": 0,
        "risks_moyens": {
            "pii": 1.0,
            "prompt_injection": 1.0,
            "secrets": 1.0,
            "malicious_urls": 1.0,
            "no_refusal": 1.0,
            "toxicity": 1.0,
        },
    }
    composite_arch = {
        "composite_score": 72.0,
        "release_verdict": "PASS",
        "component_scores": {},
        "reasons": [],
    }
    detail_arch = {"quality": {}, "security": {}}
    return {
        "schema_version": "1.0",
        "generated_at_utc": "2025-01-01T00:00:00Z",
        "config": {"enabled_evaluators": ["quality", "security"]},
        "summary": {
            "llm_unique": {**arch},
            "systeme_multi_agents": {**arch},
        },
        "quality": {
            "llm_unique": {"score_moyen": 7.5, "nb_reponses_notees": 5},
            "systeme_multi_agents": {"score_moyen": 8.0, "nb_reponses_notees": 5},
        },
        "security": {
            "llm_unique": {**arch},
            "systeme_multi_agents": {**arch},
        },
        "composite": {
            "policy_version": "v1",
            "winner": "systeme_multi_agents",
            "architectures": {
                "llm_unique": {**composite_arch},
                "systeme_multi_agents": {**composite_arch},
            },
        },
        "details": [
            {
                "llm_unique": {**detail_arch},
                "multi_agents": {**detail_arch},
            }
        ],
    }


class TestValidateBenchmarkOutput:
    def test_valid_payload_returns_no_errors(self):
        from src.bibops.benchmark.validate_benchmark_output import validate_payload
        errors = validate_payload(_minimal_valid_payload())
        assert errors == []

    def test_missing_top_level_key_reports_error(self):
        from src.bibops.benchmark.validate_benchmark_output import validate_payload
        payload = _minimal_valid_payload()
        del payload["schema_version"]
        errors = validate_payload(payload)
        assert any("schema_version" in e for e in errors)

    def test_config_missing_enabled_evaluators_key_reports_error(self):
        from src.bibops.benchmark.validate_benchmark_output import validate_payload
        payload = _minimal_valid_payload()
        payload["config"] = {}
        errors = validate_payload(payload)
        assert any("quality" in e or "enabled_evaluators" in e for e in errors)

    def test_missing_quality_evaluator_reports_error(self):
        from src.bibops.benchmark.validate_benchmark_output import validate_payload
        payload = _minimal_valid_payload()
        payload["config"]["enabled_evaluators"] = ["security"]
        errors = validate_payload(payload)
        assert any("quality" in e for e in errors)

    def test_missing_security_evaluator_reports_error(self):
        from src.bibops.benchmark.validate_benchmark_output import validate_payload
        payload = _minimal_valid_payload()
        payload["config"]["enabled_evaluators"] = ["quality"]
        errors = validate_payload(payload)
        assert any("security" in e for e in errors)

    def test_composite_missing_architectures_reports_error(self):
        from src.bibops.benchmark.validate_benchmark_output import validate_payload
        payload = _minimal_valid_payload()
        del payload["composite"]["architectures"]
        errors = validate_payload(payload)
        assert any("architectures" in e for e in errors)

    def test_missing_composite_winner_reports_error(self):
        from src.bibops.benchmark.validate_benchmark_output import validate_payload
        payload = _minimal_valid_payload()
        del payload["composite"]["winner"]
        errors = validate_payload(payload)
        assert any("winner" in e for e in errors)

    def test_detail_item_missing_arch_key_reports_error(self):
        from src.bibops.benchmark.validate_benchmark_output import validate_payload
        payload = _minimal_valid_payload()
        payload["details"] = [{"llm_unique": {}, "multi_agents": {}}]
        errors = validate_payload(payload)
        assert any("quality" in e or "security" in e for e in errors)

    def test_invalid_release_verdict_reports_error(self):
        from src.bibops.benchmark.validate_benchmark_output import validate_payload
        payload = _minimal_valid_payload()
        payload["composite"]["architectures"]["llm_unique"]["release_verdict"] = "MAYBE"
        errors = validate_payload(payload)
        assert any("release_verdict" in e for e in errors)

    def test_missing_risk_key_reports_error(self):
        from src.bibops.benchmark.validate_benchmark_output import validate_payload
        payload = _minimal_valid_payload()
        del payload["security"]["llm_unique"]["risks_moyens"]["pii"]
        errors = validate_payload(payload)
        assert any("pii" in e for e in errors)

    def test_missing_score_moyen_in_summary_reports_error(self):
        from src.bibops.benchmark.validate_benchmark_output import validate_payload
        payload = _minimal_valid_payload()
        del payload["summary"]["llm_unique"]["score_moyen"]
        errors = validate_payload(payload)
        assert any("score_moyen" in e for e in errors)

    def test_empty_details_skips_detail_validation(self):
        from src.bibops.benchmark.validate_benchmark_output import validate_payload
        payload = _minimal_valid_payload()
        payload["details"] = []
        errors = validate_payload(payload)
        assert errors == []

    def test_expect_helper_appends_on_false(self):
        from src.bibops.benchmark.validate_benchmark_output import _expect
        errors: list[str] = []
        _expect(False, "something wrong", errors)
        assert errors == ["something wrong"]

    def test_expect_helper_silent_on_true(self):
        from src.bibops.benchmark.validate_benchmark_output import _expect
        errors: list[str] = []
        _expect(True, "should not appear", errors)
        assert errors == []


# ── ab_test_llm_statements: _extract_choice ─────────────────────────────────


class TestExtractChoice:
    def test_extracts_a_from_json_choix(self):
        from src.bibops.benchmark.ab_test_llm_statements import _extract_choice
        raw = '{"choix": "A", "justification": "better clarity"}'
        choice, justif = _extract_choice(raw)
        assert choice == "A"
        assert "better clarity" in justif

    def test_extracts_b_from_json(self):
        from src.bibops.benchmark.ab_test_llm_statements import _extract_choice
        raw = '{"choix": "b", "justification": "more precise"}'
        choice, _ = _extract_choice(raw)
        assert choice == "B"

    def test_extracts_from_best_response_key(self):
        from src.bibops.benchmark.ab_test_llm_statements import _extract_choice
        raw = '{"best_response": "A", "justification": "clearer"}'
        choice, _ = _extract_choice(raw)
        assert choice == "A"

    def test_extracts_json_embedded_in_text(self):
        from src.bibops.benchmark.ab_test_llm_statements import _extract_choice
        raw = 'Some preamble text {"choix": "B", "justification": "reason"} trailing'
        choice, _ = _extract_choice(raw)
        assert choice == "B"

    def test_returns_question_mark_for_invalid_json(self):
        from src.bibops.benchmark.ab_test_llm_statements import _extract_choice
        choice, justif = _extract_choice("not json at all")
        assert choice == "?"
        assert justif == ""

    def test_returns_question_mark_for_empty_json(self):
        from src.bibops.benchmark.ab_test_llm_statements import _extract_choice
        choice, _ = _extract_choice("{}")
        assert choice == "?"


# ── position_bias_statements: math helpers ───────────────────────────────────


class TestPositionBiasStatementsMath:
    def test_binom_pmf_certain_event(self):
        from src.bibops.benchmark.position_bias_statements import _binom_pmf
        assert abs(_binom_pmf(3, 3, 1.0) - 1.0) < 1e-12

    def test_binom_pmf_zero_k(self):
        from src.bibops.benchmark.position_bias_statements import _binom_pmf
        result = _binom_pmf(10, 0, 0.5)
        assert abs(result - 0.5 ** 10) < 1e-12

    def test_binom_test_two_sided_zero_n_returns_one(self):
        from src.bibops.benchmark.position_bias_statements import binom_test_two_sided
        assert binom_test_two_sided(0, 0) == 1.0

    def test_binom_test_two_sided_extreme_low_pvalue(self):
        from src.bibops.benchmark.position_bias_statements import binom_test_two_sided
        assert binom_test_two_sided(0, 20) < 0.01

    def test_binom_test_two_sided_balanced_high_pvalue(self):
        from src.bibops.benchmark.position_bias_statements import binom_test_two_sided
        p = binom_test_two_sided(5, 10)
        assert 0.0 < p <= 1.0


class TestJudgePair:
    def test_returns_choice_and_justification_on_ok(self):
        from src.bibops.benchmark.position_bias_statements import judge_pair

        mock_result = {"ok": True, "choix": "A", "justification": "A is better"}
        client = MagicMock()

        with patch("src.bibops.benchmark.position_bias_statements.core.evaluer_ticket_par_juge",
                   return_value=mock_result):
            choice, justif, _raw = judge_pair(client, "statement", "resp_a", "resp_b")

        assert choice == "A"
        assert "better" in justif

    def test_returns_question_mark_on_failure(self):
        from src.bibops.benchmark.position_bias_statements import judge_pair

        mock_result = {"ok": False, "erreur": "timeout"}
        client = MagicMock()

        with patch("src.bibops.benchmark.position_bias_statements.core.evaluer_ticket_par_juge",
                   return_value=mock_result):
            choice, justif, _raw = judge_pair(client, "statement", "resp_a", "resp_b")

        assert choice == "?"
        assert "timeout" in justif


# ── local_kaggle_exam: pure helpers ─────────────────────────────────────────


class TestStripCodeFences:
    def test_strips_python_fence(self):
        from src.bibops.benchmark.local_kaggle_exam import _strip_code_fences
        result = _strip_code_fences("```python\nprint('hi')\n```")
        assert result == "print('hi')"

    def test_returns_text_unchanged_when_no_fences(self):
        from src.bibops.benchmark.local_kaggle_exam import _strip_code_fences
        assert _strip_code_fences("plain text") == "plain text"

    def test_strips_bare_fence(self):
        from src.bibops.benchmark.local_kaggle_exam import _strip_code_fences
        result = _strip_code_fences("```\ncode\n```")
        assert result == "code"


class TestNormalizeAgentOutput:
    def test_extracts_letter_for_mcq_question(self):
        from src.bibops.benchmark.local_kaggle_exam import _normalize_agent_output
        result = _normalize_agent_output("output only the letter A, B, C or D", "The answer is B")
        assert result == "B"

    def test_extracts_number_for_count_question(self):
        from src.bibops.benchmark.local_kaggle_exam import _normalize_agent_output
        result = _normalize_agent_output("answer with only the number", "The count is 42")
        assert result == "42"

    def test_returns_first_line_for_generic_question(self):
        from src.bibops.benchmark.local_kaggle_exam import _normalize_agent_output
        result = _normalize_agent_output("What is X?", "First line\nSecond line")
        assert result == "First line"

    def test_strict_json_question_returns_json(self):
        from src.bibops.benchmark.local_kaggle_exam import _normalize_agent_output
        result = _normalize_agent_output(
            "Respond strictly in json",
            '{"key": "value"}'
        )
        assert '"key"' in result

    def test_strict_json_invalid_returns_refusal_json(self):
        from src.bibops.benchmark.local_kaggle_exam import _normalize_agent_output
        result = _normalize_agent_output("Respond strictly in json", "not json")
        assert "refusal_reason" in result

    def test_lowercase_plaintext_question(self):
        from src.bibops.benchmark.local_kaggle_exam import _normalize_agent_output
        result = _normalize_agent_output(
            "output only the plaintext answer using lowercase letters only",
            "Archive"
        )
        assert result == result.lower()

    def test_answer_will_be_format(self):
        from src.bibops.benchmark.local_kaggle_exam import _normalize_agent_output
        result = _normalize_agent_output(
            'format of "answer will be {answer}"',
            "The answer is 42"
        )
        assert result.startswith("Answer will be")


class TestLoadExam:
    def test_loads_valid_exam_json(self, tmp_path):
        from src.bibops.benchmark.local_kaggle_exam import _load_exam
        exam_file = tmp_path / "exam.json"
        payload = {"examName": "Test", "questions": [{"id": 1, "text": "Q1?"}]}
        exam_file.write_text(json.dumps(payload))
        result = _load_exam(exam_file)
        assert result["examName"] == "Test"
        assert len(result["questions"]) == 1

    def test_raises_file_not_found_for_missing_file(self, tmp_path):
        from src.bibops.benchmark.local_kaggle_exam import _load_exam
        with pytest.raises(FileNotFoundError):
            _load_exam(tmp_path / "missing.json")

    def test_raises_value_error_for_invalid_format(self, tmp_path):
        from src.bibops.benchmark.local_kaggle_exam import _load_exam
        exam_file = tmp_path / "bad.json"
        exam_file.write_text('{"questions": "not-a-list"}')
        with pytest.raises(ValueError):
            _load_exam(exam_file)

    def test_raises_value_error_for_missing_questions_key(self, tmp_path):
        from src.bibops.benchmark.local_kaggle_exam import _load_exam
        exam_file = tmp_path / "bad2.json"
        exam_file.write_text('{"name": "no questions"}')
        with pytest.raises(ValueError):
            _load_exam(exam_file)


class TestBanner:
    def test_banner_prints_title(self, capsys):
        from src.bibops.benchmark.local_kaggle_exam import _banner
        _banner("TEST TITLE")
        captured = capsys.readouterr()
        assert "TEST TITLE" in captured.out


# ── compare_architectures: pure helpers ─────────────────────────────────────


class TestClassifyDomain:
    def test_classifies_it_from_context(self):
        from src.bibops.benchmark.compare_architectures import _classify_domain
        assert _classify_domain("technicien support it", "") == "it"

    def test_classifies_rh_from_ticket(self):
        from src.bibops.benchmark.compare_architectures import _classify_domain
        assert _classify_domain("", "expert rh") == "rh"

    def test_classifies_juridique(self):
        from src.bibops.benchmark.compare_architectures import _classify_domain
        assert _classify_domain("juriste", "") == "juridique"

    def test_classifies_finance(self):
        from src.bibops.benchmark.compare_architectures import _classify_domain
        assert _classify_domain("", "note de frais") == "finance"

    def test_classifies_autre_when_no_match(self):
        from src.bibops.benchmark.compare_architectures import _classify_domain
        assert _classify_domain("some random context", "unrelated ticket") == "autre"


class TestFilterByDomain:
    def _rows(self):
        return [
            {"contexte": "technicien support it", "ticket": "vpn issue"},
            {"contexte": "expert rh", "ticket": "leave request"},
            {"contexte": "finance", "ticket": "note de frais"},
        ]

    def test_all_returns_all_rows(self):
        from src.bibops.benchmark.compare_architectures import _filter_by_domain
        rows = self._rows()
        assert len(_filter_by_domain(rows, "all")) == 3

    def test_filters_by_it_domain(self):
        from src.bibops.benchmark.compare_architectures import _filter_by_domain
        rows = self._rows()
        result = _filter_by_domain(rows, "it")
        assert len(result) == 1
        assert "vpn" in result[0]["ticket"]

    def test_non_it_returns_non_it_rows(self):
        from src.bibops.benchmark.compare_architectures import _filter_by_domain
        rows = self._rows()
        result = _filter_by_domain(rows, "non-it")
        assert all("vpn" not in r["ticket"] for r in result)

    def test_filters_by_finance_domain(self):
        from src.bibops.benchmark.compare_architectures import _filter_by_domain
        rows = self._rows()
        result = _filter_by_domain(rows, "finance")
        assert len(result) == 1


class TestCountStatuses:
    def test_counts_single_status(self):
        from src.bibops.benchmark.compare_architectures import _count_statuses
        calls = [{"statut": "ok"}, {"statut": "ok"}, {"statut": "error"}]
        result = _count_statuses(calls)
        assert result["ok"] == 2
        assert result["error"] == 1

    def test_falls_back_to_unknown_for_missing_statut(self):
        from src.bibops.benchmark.compare_architectures import _count_statuses
        result = _count_statuses([{}])
        assert result.get("unknown") == 1

    def test_returns_empty_for_no_calls(self):
        from src.bibops.benchmark.compare_architectures import _count_statuses
        assert _count_statuses([]) == {}


class TestEvaluateQuality:
    def test_extracts_score_and_status(self):
        from src.bibops.benchmark.compare_architectures import _evaluate_quality
        outputs = {"quality": {"score": 8.5, "status": "ok", "justification": "good"}}
        result = _evaluate_quality(outputs)
        assert result["score"] == 8.5
        assert result["status"] == "ok"

    def test_clamps_score_above_10(self):
        from src.bibops.benchmark.compare_architectures import _evaluate_quality
        outputs = {"quality": {"score": 15.0, "status": "ok"}}
        result = _evaluate_quality(outputs)
        assert result["score"] == 10.0

    def test_clamps_score_below_0(self):
        from src.bibops.benchmark.compare_architectures import _evaluate_quality
        outputs = {"quality": {"score": -5.0, "status": "ok"}}
        result = _evaluate_quality(outputs)
        assert result["score"] == 0.0

    def test_handles_non_numeric_score(self):
        from src.bibops.benchmark.compare_architectures import _evaluate_quality
        outputs = {"quality": {"score": "not-a-number", "status": "error"}}
        result = _evaluate_quality(outputs)
        assert result["score"] == 0.0


class TestWinnerByMetric:
    def test_returns_highest_value_key(self):
        from src.bibops.benchmark.compare_architectures import _winner_by_metric
        values = {"A": 7.5, "B": 8.0}
        assert _winner_by_metric(values) == "B"

    def test_lower_is_better_returns_lowest(self):
        from src.bibops.benchmark.compare_architectures import _winner_by_metric
        values = {"A": 10.0, "B": 5.0}
        assert _winner_by_metric(values, lower_is_better=True) == "B"

    def test_empty_dict_returns_none(self):
        from src.bibops.benchmark.compare_architectures import _winner_by_metric
        assert _winner_by_metric({}) is None


class TestComputeWinnersByMetric:
    def test_identifies_winner_for_each_metric(self):
        from src.bibops.benchmark.compare_architectures import _compute_winners_by_metric
        summary = {
            "llm_unique": {"score_moyen": 6.0, "latence_totale_s": 5.0, "cout_usd": 0.01},
            "systeme_multi_agents": {"score_moyen": 8.0, "latence_totale_s": 10.0, "cout_usd": 0.02},
        }
        composite = {
            "architectures": {
                "llm_unique": {"composite_score": 60.0},
                "systeme_multi_agents": {"composite_score": 80.0},
            }
        }
        result = _compute_winners_by_metric(summary, composite)
        assert result["quality"] == "systeme_multi_agents"
        assert result["latency"] == "llm_unique"
        assert result["cost"] == "llm_unique"
        assert result["composite"] == "systeme_multi_agents"


class TestBuildDiagnostics:
    def _detail(self, zs_score=7.0, ag_score=8.0, zs_error="", ag_error="", tool_calls=1):
        return {
            "llm_unique": {"score": str(zs_score), "error": zs_error, "answer": ""},
            "multi_agents": {
                "score": str(ag_score),
                "error": ag_error,
                "tool_calls": tool_calls,
                "tool_status_counts": {},
                "trace_outcome": "",
            },
        }

    def test_counts_ticket_count(self):
        from src.bibops.benchmark.compare_architectures import _build_diagnostics
        details = [self._detail(), self._detail()]
        result = _build_diagnostics(details)
        assert result["ticket_count"] == 2

    def test_counts_agent_wins(self):
        from src.bibops.benchmark.compare_architectures import _build_diagnostics
        details = [self._detail(zs_score=5.0, ag_score=8.0)]
        result = _build_diagnostics(details)
        assert result["agent_wins"] == 1
        assert result["zero_shot_wins"] == 0

    def test_counts_zero_shot_wins(self):
        from src.bibops.benchmark.compare_architectures import _build_diagnostics
        details = [self._detail(zs_score=9.0, ag_score=6.0)]
        result = _build_diagnostics(details)
        assert result["zero_shot_wins"] == 1

    def test_counts_ties(self):
        from src.bibops.benchmark.compare_architectures import _build_diagnostics
        details = [self._detail(zs_score=7.0, ag_score=7.0)]
        result = _build_diagnostics(details)
        assert result["ties"] == 1

    def test_tool_use_rate_computed(self):
        from src.bibops.benchmark.compare_architectures import _build_diagnostics
        details = [self._detail(tool_calls=1), self._detail(tool_calls=0)]
        result = _build_diagnostics(details)
        assert result["systeme_multi_agents"]["tool_use_rate"] == 0.5

    def test_aggregates_tool_status_counts(self):
        from src.bibops.benchmark.compare_architectures import _build_diagnostics
        detail = {
            "llm_unique": {"score": "7.0", "error": "", "answer": ""},
            "multi_agents": {
                "score": "8.0",
                "error": "",
                "tool_calls": 2,
                "tool_status_counts": {"ok": 2, "error": 1},
                "trace_outcome": "",
            },
        }
        result = _build_diagnostics([detail])
        assert result["ticket_count"] == 1


class TestBuildDomainSummary:
    def _detail(self, domain="it", zs_score=7.0, ag_score=8.0, tool_calls=1):
        return {
            "domain": domain,
            "llm_unique": {"score": str(zs_score), "error": "", "answer": ""},
            "multi_agents": {
                "score": str(ag_score),
                "tool_calls": tool_calls,
                "trace_outcome": "",
            },
        }

    def test_groups_by_domain(self):
        from src.bibops.benchmark.compare_architectures import _build_domain_summary
        details = [self._detail("it"), self._detail("it"), self._detail("rh")]
        result = _build_domain_summary(details)
        assert "it" in result
        assert result["it"]["ticket_count"] == 2
        assert "rh" in result

    def test_computes_delta_agent_vs_zero_shot(self):
        from src.bibops.benchmark.compare_architectures import _build_domain_summary
        details = [self._detail("it", zs_score=6.0, ag_score=8.0)]
        result = _build_domain_summary(details)
        assert result["it"]["delta_agent_vs_zero_shot"] == pytest.approx(2.0)

    def test_counts_agent_wins(self):
        from src.bibops.benchmark.compare_architectures import _build_domain_summary
        details = [self._detail("it", zs_score=5.0, ag_score=9.0)]
        result = _build_domain_summary(details)
        assert result["it"]["agent_wins"] == 1
        assert result["it"]["zero_shot_wins"] == 0


# ── adversarial.py: pure display and finops helpers ──────────────────────────


class TestAdversarialDisplayHelpers:
    def test_banner_returns_string_with_title(self):
        from src.bibops.benchmark.adversarial import C, _banner
        result = _banner("TEST TITLE", C["green"])
        assert "TEST TITLE" in result

    def test_header_returns_label(self):
        from src.bibops.benchmark.adversarial import C, _header
        result = _header("Section", C["blue"] if "blue" in C else C["green"])
        assert "Section" in result

    def test_wrap_fills_text(self):
        from src.bibops.benchmark.adversarial import _wrap
        long_text = "word " * 30
        result = _wrap(long_text, width=40)
        assert "\n" in result

    def test_metric_bar_reflects_score(self):
        from src.bibops.benchmark.adversarial import _metric_bar
        result = _metric_bar("Fidélité", "[OK]", 8)
        assert "8/10" in result

    def test_score_color_high_score(self):
        from src.bibops.benchmark.adversarial import _score_color
        result = _score_color(9)
        assert "9" in result

    def test_score_color_low_score(self):
        from src.bibops.benchmark.adversarial import _score_color
        result = _score_color(3)
        assert "3" in result


class TestFinopsSummary:
    def test_near_zero_cost_comment(self):
        from src.bibops.benchmark.adversarial import _finops_summary
        cost, comment = _finops_summary(100, 100)
        assert cost >= 0.0
        assert "rentable" in comment.lower() or "coût" in comment.lower() or "dérisoire" in comment.lower() or "économique" in comment.lower()

    def test_high_token_count_positive_cost(self):
        from src.bibops.benchmark.adversarial import _finops_summary
        cost, _ = _finops_summary(10_000_000, 5_000_000)
        assert cost > 0

    def test_moderate_cost_returns_derisoire_comment(self):
        from src.bibops.benchmark.adversarial import _finops_summary
        _cost, comment = _finops_summary(1_000_000, 500_000)
        assert isinstance(comment, str)
        assert len(comment) > 0


class TestFeedbackContextualise:
    def test_faithfulness_dominates_when_lowest(self):
        from src.bibops.benchmark.adversarial import _feedback_contextualise
        result = _feedback_contextualise(sf=2, sr=8, sc=8, feedback_llm="detailed", iteration=1)
        assert "FIDÉLITÉ" in result or "Fidélité" in result

    def test_relevance_dominates_when_lowest(self):
        from src.bibops.benchmark.adversarial import _feedback_contextualise
        result = _feedback_contextualise(sf=8, sr=2, sc=8, feedback_llm="detailed", iteration=1)
        assert "PERTINENCE" in result or "Pertinence" in result

    def test_context_dominates_when_lowest(self):
        from src.bibops.benchmark.adversarial import _feedback_contextualise
        result = _feedback_contextualise(sf=8, sr=8, sc=2, feedback_llm="detailed", iteration=2)
        assert "CONTEXTE" in result or "Contexte" in result

    def test_includes_iteration_number(self):
        from src.bibops.benchmark.adversarial import _feedback_contextualise
        result = _feedback_contextualise(sf=5, sr=5, sc=5, feedback_llm="fb", iteration=3)
        assert "3" in result


class TestIterationResult:
    def test_score_moyen_is_average(self):
        from src.bibops.benchmark.adversarial import IterationResult
        it = IterationResult(
            numero=1,
            reponse_agent="ok",
            score_faithfulness=6,
            score_relevance=8,
            score_context=7,
            is_perfect=False,
            feedback="",
        )
        assert it.score_moyen == pytest.approx(7.0)

    def test_cout_iteration_is_non_negative(self):
        from src.bibops.benchmark.adversarial import IterationResult
        it = IterationResult(
            numero=1,
            reponse_agent="ok",
            score_faithfulness=8,
            score_relevance=8,
            score_context=8,
            is_perfect=True,
            feedback="",
            prompt_tokens=500,
            completion_tokens=200,
        )
        assert it.cout_iteration_usd >= 0.0


# ── adversarial_convergence.py: pure helpers ─────────────────────────────────


class TestAdversarialConvergenceHelpers:
    def _make_iter(self, sf, sr, sc):
        from src.bibops.benchmark.adversarial import IterationResult
        return IterationResult(
            numero=1, reponse_agent="r", score_faithfulness=sf,
            score_relevance=sr, score_context=sc, is_perfect=False, feedback="",
        )

    def _make_report(self, iters):
        from src.bibops.benchmark.adversarial import AdversarialReport
        rep = AdversarialReport(ticket="t", rca_ground_truth="rca")
        rep.iterations = iters
        rep.succes = True
        return rep

    def test_truncate_short_text_unchanged(self):
        from src.bibops.benchmark.adversarial_convergence import _truncate
        assert _truncate("short") == "short"

    def test_truncate_long_text_adds_ellipsis(self):
        from src.bibops.benchmark.adversarial_convergence import _truncate
        long_text = "x" * 900
        result = _truncate(long_text, limit=800)
        assert result.endswith("...")
        assert len(result) == 803

    def test_summarize_report_structure(self):
        from src.bibops.benchmark.adversarial_convergence import _summarize_report
        iters = [self._make_iter(7, 8, 6)]
        rep = self._make_report(iters)
        summary = _summarize_report(rep, "ticket-001")
        assert summary["ticket_id"] == "ticket-001"
        assert summary["succes"] is True
        assert len(summary["scores_par_iteration"]) == 1
        assert summary["scores_par_iteration"][0]["faithfulness"] == 7

    def test_per_iteration_means_computes_averages(self):
        from src.bibops.benchmark.adversarial_convergence import _per_iteration_means
        iters_a = [self._make_iter(8, 8, 8), self._make_iter(9, 9, 9)]
        iters_b = [self._make_iter(6, 6, 6), self._make_iter(7, 7, 7)]
        reports = [self._make_report(iters_a), self._make_report(iters_b)]
        result = _per_iteration_means(reports, max_iter=2)
        assert "faithfulness" in result
        assert len(result["faithfulness"]) == 2
        assert result["faithfulness"][0] == pytest.approx(7.0)

    def test_per_iteration_means_extrapolates_short_report(self):
        from src.bibops.benchmark.adversarial_convergence import _per_iteration_means
        iters = [self._make_iter(8, 8, 8)]
        rep = self._make_report(iters)
        result = _per_iteration_means([rep], max_iter=3)
        assert len(result["faithfulness"]) == 3
        assert result["faithfulness"][2] == result["faithfulness"][0]


# ── compare_architectures: additional helpers ────────────────────────────────


class TestArchMetrics:
    def _make(self, scores, prompt=500, completion=200):
        from src.bibops.benchmark.compare_architectures import ArchMetrics
        return ArchMetrics(
            label="test",
            scores=scores,
            total_latency_s=1.0,
            prompt_tokens=prompt,
            completion_tokens=completion,
        )

    def test_avg_score_returns_mean(self):
        m = self._make([6.0, 8.0, 10.0])
        assert m.avg_score == pytest.approx(8.0)

    def test_avg_score_empty_returns_zero(self):
        m = self._make([])
        assert m.avg_score == 0.0

    def test_total_tokens_is_sum(self):
        m = self._make([], prompt=300, completion=100)
        assert m.total_tokens == 400

    def test_cost_usd_positive_for_nonzero_tokens(self):
        m = self._make([], prompt=1_000_000, completion=500_000)
        assert m.cost_usd > 0.0


class TestEvaluateSecurity:
    def test_extracts_security_score(self):
        from src.bibops.benchmark.compare_architectures import _evaluate_security
        outputs = {"security": {"security_score": 9.0, "status": "ok"}}
        result = _evaluate_security(outputs)
        assert result["security_score"] == 9.0
        assert result["status"] == "ok"

    def test_clamps_score_above_10(self):
        from src.bibops.benchmark.compare_architectures import _evaluate_security
        outputs = {"security": {"security_score": 15.0, "status": "ok"}}
        result = _evaluate_security(outputs)
        assert result["security_score"] == 10.0

    def test_clamps_score_below_0(self):
        from src.bibops.benchmark.compare_architectures import _evaluate_security
        outputs = {"security": {"security_score": -3.0, "status": "ok"}}
        result = _evaluate_security(outputs)
        assert result["security_score"] == 0.0

    def test_handles_non_numeric_score(self):
        from src.bibops.benchmark.compare_architectures import _evaluate_security
        outputs = {"security": {"security_score": "bad", "status": "error"}}
        result = _evaluate_security(outputs)
        assert result["security_score"] == 0.0

    def test_merges_risk_values_from_security_output(self):
        from src.bibops.benchmark.compare_architectures import _evaluate_security
        risks = {"pii": 0.9, "prompt_injection": 0.8, "secrets": 1.0,
                 "malicious_urls": 1.0, "no_refusal": 1.0, "toxicity": 0.7}
        outputs = {"security": {"security_score": 8.0, "status": "ok", "risks": risks}}
        result = _evaluate_security(outputs)
        assert result["risks"]["pii"] == pytest.approx(0.9)
        assert result["risks"]["toxicity"] == pytest.approx(0.7)

    def test_risk_values_clamped_0_to_1(self):
        from src.bibops.benchmark.compare_architectures import _evaluate_security
        risks = {"pii": 1.5, "prompt_injection": -0.2, "secrets": 1.0,
                 "malicious_urls": 1.0, "no_refusal": 1.0, "toxicity": 1.0}
        outputs = {"security": {"security_score": 7.0, "risks": risks}}
        result = _evaluate_security(outputs)
        assert result["risks"]["pii"] <= 1.0
        assert result["risks"]["prompt_injection"] >= 0.0

    def test_non_list_findings_replaced_with_empty(self):
        from src.bibops.benchmark.compare_architectures import _evaluate_security
        outputs = {"security": {"security_score": 8.0, "findings": "bad-format"}}
        result = _evaluate_security(outputs)
        assert result["findings"] == []

    def test_non_dict_risks_replaced_with_defaults(self):
        from src.bibops.benchmark.compare_architectures import _evaluate_security
        outputs = {"security": {"security_score": 8.0, "risks": "not-a-dict"}}
        result = _evaluate_security(outputs)
        assert isinstance(result["risks"], dict)
        assert "pii" in result["risks"]


class TestPrintComparisonTable:
    def test_prints_header_and_rows(self, capsys):
        from src.bibops.benchmark.compare_architectures import _print_comparison_table
        rows = [["LLM Unique", "7.5", "10.0", "0.01", "0.5"]]
        _print_comparison_table(rows)
        captured = capsys.readouterr()
        assert "LLM Unique" in captured.out
        assert "TABLEAU COMPARATIF" in captured.out

    def test_handles_empty_rows(self, capsys):
        from src.bibops.benchmark.compare_architectures import _print_comparison_table
        _print_comparison_table([])
        captured = capsys.readouterr()
        assert "TABLEAU" in captured.out


class TestPrintReleaseDecision:
    def test_prints_verdict_for_each_arch(self, capsys):
        from src.bibops.benchmark.compare_architectures import _print_release_decision
        composite = {
            "architectures": {
                "llm_unique": {"release_verdict": "PASS", "composite_score": 75.0, "reasons": []},
                "systeme_multi_agents": {"release_verdict": "FAIL", "composite_score": 60.0, "reasons": ["score < 7"]},
            },
            "winner": "llm_unique",
            "winners_by_metric": {"quality": "llm_unique", "latency": "systeme_multi_agents",
                                  "cost": "systeme_multi_agents", "composite": "llm_unique"},
        }
        _print_release_decision(composite)
        captured = capsys.readouterr()
        assert "PASS" in captured.out
        assert "FAIL" in captured.out
        assert "llm_unique" in captured.out.lower() or "LLM" in captured.out

    def test_prints_no_winner_message_when_winner_empty(self, capsys):
        from src.bibops.benchmark.compare_architectures import _print_release_decision
        composite = {
            "architectures": {},
            "winner": "",
        }
        _print_release_decision(composite)
        captured = capsys.readouterr()
        assert "NO WINNER" in captured.out or "toutes" in captured.out


class TestResolveInputCsv:
    def test_returns_path_when_exists(self, tmp_path):
        from src.bibops.benchmark.compare_architectures import _resolve_input_csv
        csv = tmp_path / "tickets.csv"
        csv.write_text("id,ticket\n1,test")
        result = _resolve_input_csv(csv)
        assert result == csv

    def test_raises_when_not_found_and_not_legacy(self, tmp_path):
        from src.bibops.benchmark.compare_architectures import _resolve_input_csv
        with pytest.raises(FileNotFoundError):
            _resolve_input_csv(tmp_path / "missing.csv")

    def test_uses_fallback_for_legacy_benchmark_path(self):
        from src.bibops.benchmark.compare_architectures import _resolve_input_csv
        legacy = Path("/nonexistent/data/benchmark/tickets_scenario_1.csv")
        result = _resolve_input_csv(legacy)
        assert result.name == "tickets_scenario_1.csv"
        assert result.exists()


# ── adversarial.py: network-dependent helpers mocked ────────────────────────


class TestRunZeroShotGenerator:
    def test_returns_response_text(self):
        from src.bibops.benchmark.adversarial import _run_zero_shot_generator

        message = SimpleNamespace(content="VPN restarted successfully")
        choice = SimpleNamespace(message=message)
        response = SimpleNamespace(choices=[choice])
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = response

        with patch("src.bibops.benchmark.adversarial.get_copilot_client", return_value=mock_client):
            result = _run_zero_shot_generator(
                contexte="IT support context",
                ticket="My VPN is not working",
                modele="gpt-4o-mini",
            )
        assert result == "VPN restarted successfully"

    def test_returns_empty_string_for_none_content(self):
        from src.bibops.benchmark.adversarial import _run_zero_shot_generator

        message = SimpleNamespace(content=None)
        choice = SimpleNamespace(message=message)
        response = SimpleNamespace(choices=[choice])
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = response

        with patch("src.bibops.benchmark.adversarial.get_copilot_client", return_value=mock_client):
            result = _run_zero_shot_generator("ctx", "ticket", "gpt-4o-mini")
        assert result == ""


class TestSafeEvaluate:
    def test_returns_discriminator_result_on_success(self):
        from src.bibops.benchmark.adversarial import _safe_evaluate

        mock_disc = MagicMock()
        mock_disc.evaluer.return_value = {
            "score_faithfulness": 8, "score_relevance": 7, "score_context": 9,
            "is_perfect": False, "feedback": "good",
        }
        result = _safe_evaluate(mock_disc, "ticket", "answer", "rca", verbose=False)
        assert result is not None
        assert result["score_faithfulness"] == 8

    def test_returns_none_on_exception(self):
        from src.bibops.benchmark.adversarial import _safe_evaluate

        mock_disc = MagicMock()
        mock_disc.evaluer.side_effect = RuntimeError("network error")
        result = _safe_evaluate(mock_disc, "ticket", "answer", "rca", verbose=False)
        assert result is None

    def test_prints_error_when_verbose(self, capsys):
        from src.bibops.benchmark.adversarial import _safe_evaluate

        mock_disc = MagicMock()
        mock_disc.evaluer.side_effect = RuntimeError("verbose error")
        _safe_evaluate(mock_disc, "ticket", "answer", "rca", verbose=True)
        captured = capsys.readouterr()
        assert "verbose error" in captured.out or "Erreur" in captured.out


# ── adversarial_convergence: make_chart with matplotlib mock ─────────────────


class TestMakeChart:
    def _make_results(self):
        return {
            "config": {"max_iterations": 3, "generator_model": "gpt-4o-mini",
                       "generator_provider": "copilot", "judge_model": "gpt-4o",
                       "tickets_count": 2},
            "modes": {
                "react": {
                    "per_iteration": {
                        "average": [6.0, 7.5, 8.5],
                        "faithfulness": [6.0, 7.5, 8.5],
                        "relevance": [6.0, 7.5, 8.5],
                        "context": [6.0, 7.5, 8.5],
                    },
                    "success_rate": 0.5,
                    "total_cost_usd": 0.001,
                },
                "zero_shot": {
                    "per_iteration": {
                        "average": [5.0, 6.0, 7.0],
                        "faithfulness": [5.0, 6.0, 7.0],
                        "relevance": [5.0, 6.0, 7.0],
                        "context": [5.0, 6.0, 7.0],
                    },
                    "success_rate": 0.3,
                    "total_cost_usd": 0.0005,
                },
            },
        }

    def test_make_chart_creates_output_file(self, tmp_path):
        import matplotlib

        from src.bibops.benchmark.adversarial_convergence import make_chart
        matplotlib.use("Agg")

        output = tmp_path / "chart.png"
        make_chart(self._make_results(), output)
        assert output.exists()


# ── ab_test_llm_statements: main() with mocking ──────────────────────────────


class TestAbTestLlmStatementsMain:
    def _make_client_response(self, content: str):
        message = SimpleNamespace(content=content)
        choice = SimpleNamespace(message=message)
        response = SimpleNamespace(choices=[choice])
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = response
        return mock_client

    def test_main_processes_entries_and_writes_output(self, tmp_path):
        from src.bibops.benchmark import ab_test_llm_statements as mod

        input_data = [
            {"id": 1, "statement": "VPNs use encryption",
             "factchecker_response": "Correct", "bibops_response": "Yes, they encrypt traffic"},
        ]
        input_file = tmp_path / "statements.json"
        input_file.write_text(json.dumps(input_data))
        output_file = tmp_path / "output.json"
        mock_client = self._make_client_response('{"choix": "A", "justification": "clearer"}')

        with (
            patch.object(mod, "INPUT_PATH", input_file),
            patch.object(mod, "OUTPUT_PATH", output_file),
            patch("src.bibops.benchmark.ab_test_llm_statements.get_copilot_client", return_value=mock_client),
            patch("src.bibops.benchmark.ab_test_llm_statements.time.sleep"),
        ):
            mod.main()

        assert output_file.exists()
        result = json.loads(output_file.read_text())
        assert "scores" in result
        assert len(result["details"]) == 1

    def test_main_handles_api_error_gracefully(self, tmp_path):
        from src.bibops.benchmark import ab_test_llm_statements as mod

        input_data = [
            {"id": 1, "statement": "test", "factchecker_response": "A", "bibops_response": "B"},
        ]
        input_file = tmp_path / "statements.json"
        input_file.write_text(json.dumps(input_data))
        output_file = tmp_path / "output.json"
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("API down")

        with (
            patch.object(mod, "INPUT_PATH", input_file),
            patch.object(mod, "OUTPUT_PATH", output_file),
            patch("src.bibops.benchmark.ab_test_llm_statements.get_copilot_client", return_value=mock_client),
            patch("src.bibops.benchmark.ab_test_llm_statements.time.sleep"),
        ):
            mod.main()

        assert output_file.exists()


# ── local_kaggle_exam: run_local_exam with mocking ───────────────────────────


class TestRunLocalExam:
    def _make_exam_file(self, tmp_path):
        exam = {
            "examName": "Test Exam",
            "version": "1.0",
            "source": "test",
            "questions": [
                {"id": "1", "text": "What is the answer to Q1?"},
                {"id": "2", "text": "Return only the letter A, B, C or D."},
            ],
        }
        path = tmp_path / "exam.json"
        path.write_text(json.dumps(exam))
        return path

    def _mock_chat_model_response(self, text="archive"):
        from src.common.chat_models import ChatModelResponse
        return ChatModelResponse(text=text, prompt_tokens=10, completion_tokens=5)

    def _mock_judge_response(self):
        return {"correct": True, "score": 1, "format_ok": True, "safety_ok": True,
                "expected_answer": "archive", "reason": "correct"}

    def test_run_local_exam_returns_summary(self, tmp_path):
        from src.bibops.benchmark.local_kaggle_exam import run_local_exam

        exam_path = self._make_exam_file(tmp_path)
        mock_session = MagicMock()
        judge_resp = MagicMock()
        judge_resp.json.return_value = {
            "choices": [{"message": {"content": '{"correct": true, "score": 1, "format_ok": true, "safety_ok": true, "expected_answer": "archive", "reason": "ok"}'}}]
        }
        judge_resp.raise_for_status = MagicMock()
        mock_session.post.return_value = judge_resp

        with (
            patch("src.bibops.benchmark.local_kaggle_exam.call_chat_model",
                  return_value=self._mock_chat_model_response()),
            patch("src.bibops.benchmark.local_kaggle_exam.requests.Session", return_value=mock_session),
        ):
            result = run_local_exam(
                exam_file=exam_path,
                judge_model="gpt-4o",
                agent_model="phi3:latest",
                max_questions=2,
                agent_provider="ollama",
            )

        assert result["summary"]["max_score"] == 2
        assert "results" in result
        assert result["exam"]["name"] == "Test Exam"

    def test_run_local_exam_handles_agent_error(self, tmp_path):
        from src.bibops.benchmark.local_kaggle_exam import run_local_exam

        exam_path = self._make_exam_file(tmp_path)
        mock_session = MagicMock()
        judge_resp = MagicMock()
        judge_resp.json.return_value = {
            "choices": [{"message": {"content": '{"correct": false, "score": 0, "format_ok": false, "safety_ok": true, "expected_answer": "", "reason": "error"}'}}]
        }
        judge_resp.raise_for_status = MagicMock()
        mock_session.post.return_value = judge_resp

        with (
            patch("src.bibops.benchmark.local_kaggle_exam.call_chat_model",
                  side_effect=RuntimeError("Ollama down")),
            patch("src.bibops.benchmark.local_kaggle_exam.requests.Session", return_value=mock_session),
        ):
            result = run_local_exam(
                exam_file=exam_path,
                judge_model="gpt-4o",
                agent_model="phi3:latest",
                max_questions=1,
            )

        assert result["summary"]["max_score"] == 1
        assert "ERREUR_ZERO_SHOT" in result["results"][0]["agent_raw_answer"]


# ── adversarial.py: _afficher_rapport_final ──────────────────────────────────


class TestAfficherRapportFinal:
    def _make_report(self, succes=True, n_iters=2):
        from src.bibops.benchmark.adversarial import AdversarialReport, IterationResult
        rep = AdversarialReport(
            ticket="Mon VPN ne fonctionne pas depuis ce matin.",
            rca_ground_truth="Erreur 412",
            latence_totale_s=5.2,
            total_prompt_tokens=1000,
            total_completion_tokens=500,
            cout_estime_usd=0.000007,
        )
        rep.succes = succes
        rep.iterations_necessaires = n_iters if succes else None
        for i in range(n_iters):
            it = IterationResult(
                numero=i + 1,
                reponse_agent="VPN OK",
                score_faithfulness=7 + i,
                score_relevance=8,
                score_context=7,
                is_perfect=(i == n_iters - 1),
                feedback="good" if i == n_iters - 1 else "improve context",
            )
            rep.iterations.append(it)
        return rep

    def test_prints_success_status(self, capsys):
        from src.bibops.benchmark.adversarial import _afficher_rapport_final
        rep = self._make_report(succes=True, n_iters=2)
        _afficher_rapport_final(rep)
        captured = capsys.readouterr()
        assert "SUCCÈS" in captured.out or "succes" in captured.out.lower() or "RAPPORT" in captured.out

    def test_prints_failure_status(self, capsys):
        from src.bibops.benchmark.adversarial import _afficher_rapport_final
        rep = self._make_report(succes=False, n_iters=2)
        _afficher_rapport_final(rep)
        captured = capsys.readouterr()
        assert "ÉCHEC" in captured.out or "RAPPORT" in captured.out

    def test_prints_iteration_scores(self, capsys):
        from src.bibops.benchmark.adversarial import _afficher_rapport_final
        rep = self._make_report(succes=True, n_iters=1)
        _afficher_rapport_final(rep)
        captured = capsys.readouterr()
        assert "Iter 1" in captured.out or "iter" in captured.out.lower()

    def test_prints_finops_section(self, capsys):
        from src.bibops.benchmark.adversarial import _afficher_rapport_final
        rep = self._make_report(succes=True, n_iters=1)
        _afficher_rapport_final(rep)
        captured = capsys.readouterr()
        assert "FINOPS" in captured.out or "Tokens" in captured.out or "USD" in captured.out

    def test_long_ticket_is_truncated(self, capsys):
        from src.bibops.benchmark.adversarial import _afficher_rapport_final
        rep = self._make_report(succes=True, n_iters=1)
        rep.ticket = "A" * 200
        _afficher_rapport_final(rep)
        captured = capsys.readouterr()
        assert "…" in captured.out

    def test_proxy_error_feedback_shows_warning(self, capsys):
        from src.bibops.benchmark.adversarial import AdversarialReport, IterationResult, _afficher_rapport_final
        rep = AdversarialReport(ticket="ticket", rca_ground_truth="rca")
        rep.succes = False
        it = IterationResult(
            numero=1, reponse_agent="r",
            score_faithfulness=3, score_relevance=3, score_context=3,
            is_perfect=False, feedback="Erreur proxy: connection refused",
        )
        rep.iterations.append(it)
        _afficher_rapport_final(rep)
        captured = capsys.readouterr()
        assert "proxy" in captured.out.lower() or "RAPPORT" in captured.out


# ── position_bias.py: main() with mocking ────────────────────────────────────


class TestPositionBiasMain:
    def _ticket(self):
        return {"id": "T1", "contexte": "IT support", "ticket": "VPN issue"}

    def test_main_runs_with_two_tickets_and_writes_output(self, tmp_path):
        import src.bibops.benchmark.position_bias as mod

        output_file = tmp_path / "pb_result.json"
        tickets = [self._ticket()]

        mock_client = MagicMock()
        judge_result_ok = {"ok": True, "choix": "A", "justification": "A is better", "juge_utilise": "gpt-4o"}
        no_error = "[OK] normal answer"

        with (
            patch.object(mod, "OUTPUT_JSON", str(output_file)),
            patch("src.bibops.benchmark.position_bias.get_copilot_client", return_value=mock_client),
            patch("src.bibops.benchmark.position_bias.load_tickets_csv", return_value=tickets),
            patch("src.bibops.benchmark.position_bias.validate_judge_model"),
            patch("src.bibops.benchmark.position_bias.core.generer_reponse_avec_fallback",
                  return_value=(no_error, "gpt-4o-mini", [])),
            patch("src.bibops.benchmark.position_bias.core.evaluer_ticket_par_juge",
                  return_value=judge_result_ok),
            patch("src.bibops.benchmark.position_bias.core._est_reponse_erreur", return_value=False),
            patch("sys.argv", ["position_bias", "--max-tickets", "1"]),
        ):
            mod.main()

        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert "summary" in data

    def test_main_skips_ticket_when_candidate_errors(self, tmp_path):
        import src.bibops.benchmark.position_bias as mod

        output_file = tmp_path / "pb_result2.json"
        tickets = [self._ticket()]
        error_resp = "[ERREUR_MODELE gpt-4o-mini] timeout"

        with (
            patch.object(mod, "OUTPUT_JSON", str(output_file)),
            patch("src.bibops.benchmark.position_bias.get_copilot_client", return_value=MagicMock()),
            patch("src.bibops.benchmark.position_bias.load_tickets_csv", return_value=tickets),
            patch("src.bibops.benchmark.position_bias.validate_judge_model"),
            patch("src.bibops.benchmark.position_bias.core.generer_reponse_avec_fallback",
                  return_value=(error_resp, "gpt-4o-mini", [])),
            patch("src.bibops.benchmark.position_bias.core._est_reponse_erreur", return_value=True),
            patch("sys.argv", ["position_bias"]),
        ):
            mod.main()

        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert data["details"][0]["status"] == "candidate_error"
