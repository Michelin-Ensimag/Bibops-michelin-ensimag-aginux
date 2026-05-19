"""Extra coverage for benchmark/runners: pure helpers not covered by other tests."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# position_bias: pure math helpers
# ---------------------------------------------------------------------------

class TestBinomPmf:
    def test_zero_k(self):
        from src.bibops.benchmark.position_bias import _binom_pmf
        result = _binom_pmf(10, 0, 0.5)
        assert abs(result - (0.5 ** 10)) < 1e-12

    def test_all_successes(self):
        from src.bibops.benchmark.position_bias import _binom_pmf
        result = _binom_pmf(5, 5, 0.5)
        assert abs(result - (0.5 ** 5)) < 1e-12

    def test_mid_point(self):
        from src.bibops.benchmark.position_bias import _binom_pmf
        result = _binom_pmf(4, 2, 0.5)
        assert result > 0

    def test_certain_event_at_k_n(self):
        from src.bibops.benchmark.position_bias import _binom_pmf
        # p=1.0, k=n → result = 1.0
        result = _binom_pmf(3, 3, 1.0)
        assert abs(result - 1.0) < 1e-12


class TestBinomTestTwoSided:
    def test_zero_n_returns_one(self):
        from src.bibops.benchmark.position_bias import binom_test_two_sided
        assert binom_test_two_sided(0, 0) == 1.0

    def test_negative_n_returns_one(self):
        from src.bibops.benchmark.position_bias import binom_test_two_sided
        assert binom_test_two_sided(0, -1) == 1.0

    def test_unbiased_center(self):
        from src.bibops.benchmark.position_bias import binom_test_two_sided
        # k=n/2 → high p-value (no bias evidence)
        p = binom_test_two_sided(5, 10)
        assert 0.0 < p <= 1.0

    def test_extreme_result_low_pvalue(self):
        from src.bibops.benchmark.position_bias import binom_test_two_sided
        # k=0, n=20 → very unlikely under fair coin
        p = binom_test_two_sided(0, 20)
        assert p < 0.01

    def test_result_clamped_to_one(self):
        from src.bibops.benchmark.position_bias import binom_test_two_sided
        # p=0.5, k=n/2 → sum of all probs ≈ 1.0
        p = binom_test_two_sided(1, 2)
        assert p <= 1.0

    def test_all_trials_same_outcome(self):
        from src.bibops.benchmark.position_bias import binom_test_two_sided
        p = binom_test_two_sided(10, 10)
        assert p < 0.01  # very significant


# ---------------------------------------------------------------------------
# ab_test_user: env helpers and appeler_modele
# ---------------------------------------------------------------------------

class TestEnvInt:
    def test_missing_env_returns_default(self, monkeypatch):
        monkeypatch.delenv("SOME_VAR", raising=False)
        from src.bibops.benchmark.ab_test_user import _env_int
        assert _env_int("SOME_VAR", 42) == 42

    def test_valid_positive_int(self, monkeypatch):
        monkeypatch.setenv("SOME_VAR", "7")
        from src.bibops.benchmark.ab_test_user import _env_int
        assert _env_int("SOME_VAR", 42) == 7

    def test_zero_or_negative_returns_default(self, monkeypatch):
        monkeypatch.setenv("SOME_VAR", "0")
        from src.bibops.benchmark.ab_test_user import _env_int
        assert _env_int("SOME_VAR", 5) == 5

    def test_non_int_returns_default(self, monkeypatch):
        monkeypatch.setenv("SOME_VAR", "abc")
        from src.bibops.benchmark.ab_test_user import _env_int
        assert _env_int("SOME_VAR", 3) == 3

    def test_empty_string_returns_default(self, monkeypatch):
        monkeypatch.setenv("SOME_VAR", "  ")
        from src.bibops.benchmark.ab_test_user import _env_int
        assert _env_int("SOME_VAR", 99) == 99


class TestAutoChoiceDefault:
    def test_default_is_a(self, monkeypatch):
        monkeypatch.delenv("BIBOPS_AB_USER_CHOICE", raising=False)
        from src.bibops.benchmark.ab_test_user import _auto_choice_default
        assert _auto_choice_default() == "A"

    def test_b_from_env(self, monkeypatch):
        monkeypatch.setenv("BIBOPS_AB_USER_CHOICE", "B")
        from src.bibops.benchmark.ab_test_user import _auto_choice_default
        assert _auto_choice_default() == "B"

    def test_invalid_falls_back_to_a(self, monkeypatch):
        monkeypatch.setenv("BIBOPS_AB_USER_CHOICE", "X")
        from src.bibops.benchmark.ab_test_user import _auto_choice_default
        assert _auto_choice_default() == "A"

    def test_lowercase_normalized(self, monkeypatch):
        monkeypatch.setenv("BIBOPS_AB_USER_CHOICE", "b")
        from src.bibops.benchmark.ab_test_user import _auto_choice_default
        assert _auto_choice_default() == "B"


class TestIsNonInteractiveMode:
    def test_env_flag_set(self, monkeypatch):
        monkeypatch.setenv("BIBOPS_NON_INTERACTIVE", "1")
        from src.bibops.benchmark.ab_test_user import _is_non_interactive_mode
        assert _is_non_interactive_mode() is True

    def test_env_flag_not_set_returns_bool(self, monkeypatch):
        monkeypatch.delenv("BIBOPS_NON_INTERACTIVE", raising=False)
        from src.bibops.benchmark.ab_test_user import _is_non_interactive_mode
        assert isinstance(_is_non_interactive_mode(), bool)


class TestAppelerModeleUser:
    def _make_response(self, content: str):
        msg = MagicMock()
        msg.content = content
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]
        return resp

    def test_returns_content_on_success(self):
        from src.bibops.benchmark.ab_test_user import _call
        client = MagicMock()
        client.chat.completions.create.return_value = self._make_response("VPN OK")
        with patch("src.bibops.benchmark.ab_test_user.get_copilot_client", return_value=client):
            result = _call("gpt-4o-mini", "ctx", "ticket", retries=1)
        assert result == "VPN OK"

    def test_retries_on_exception(self):
        from src.bibops.benchmark.ab_test_user import _call
        client = MagicMock()
        call_count = [0]
        def side_effect(**kwargs):
            call_count[0] += 1
            if call_count[0] < 2:
                raise RuntimeError("transient error")
            return self._make_response("recovered")
        client.chat.completions.create.side_effect = side_effect
        with patch("src.bibops.benchmark.ab_test_user.get_copilot_client", return_value=client), \
             patch("src.bibops.benchmark.ab_test_user.time.sleep"):
            result = _call("gpt-4o-mini", "ctx", "ticket", retries=2)
        assert result == "recovered"
        assert call_count[0] == 2

    def test_all_retries_fail_returns_error_string(self):
        from src.bibops.benchmark.ab_test_user import _call
        client = MagicMock()
        client.chat.completions.create.side_effect = RuntimeError("always fails")
        with patch("src.bibops.benchmark.ab_test_user.get_copilot_client", return_value=client), \
             patch("src.bibops.benchmark.ab_test_user.time.sleep"):
            result = _call("gpt-4o-mini", "ctx", "ticket", retries=2)
        assert "ERREUR_MODELE" in result
        assert "always fails" in result


# ---------------------------------------------------------------------------
# core.py: EOFError path in demander_feedback_utilisateur
# ---------------------------------------------------------------------------

class TestDemanderFeedbackEOF:
    def test_eof_returns_default(self, monkeypatch):
        monkeypatch.delenv("BIBOPS_NON_INTERACTIVE", raising=False)
        monkeypatch.delenv("BIBOPS_DEFAULT_FEEDBACK", raising=False)
        # Make stdin look like a tty so non-interactive check passes,
        # then raise EOFError on input()
        with patch("src.bibops.benchmark.core.sys.stdin") as fake_stdin, \
             patch("builtins.input", side_effect=EOFError()):
            fake_stdin.isatty.return_value = True
            from src.bibops.benchmark.core import demander_feedback_utilisateur
            result = demander_feedback_utilisateur()
        # Should return a valid feedback string (default "2" = Partiellement utile)
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# ab_test_llm.py: missed branches
# ---------------------------------------------------------------------------

def _make_response(content: str):
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


class TestAppelerJugeMissedBranches:
    def test_retry_strict_prompt_also_fails(self):
        """Both JSON attempts fail → None, 'JSON invalide'."""
        from src.bibops.benchmark.ab_test_llm import appeler_juge

        call_count = [0]
        def fake_timeout(fn, _):
            call_count[0] += 1
            return _make_response("not json")

        client = MagicMock()
        with patch("src.bibops.benchmark.ab_test_llm._executer_avec_timeout", side_effect=fake_timeout):
            result, _err = appeler_juge(client, "gpt-4o", "prompt")

        assert result is None
        assert call_count[0] == 2  # both strict and normal attempted

    def test_invalid_choix_field_returns_none(self):
        """Valid JSON but choix field not A/B → None, 'Champ choix invalide'."""
        from src.bibops.benchmark.ab_test_llm import appeler_juge

        client = MagicMock()
        with patch("src.bibops.benchmark.ab_test_llm._executer_avec_timeout",
                   side_effect=lambda fn, _: fn()):
            client.chat.completions.create.return_value = _make_response(
                '{"choix": "C", "justification": "neither"}'
            )
            result, err = appeler_juge(client, "gpt-4o", "prompt")

        assert result is None
        assert "choix" in err.lower() or err == "Champ choix invalide"


class TestGenererReponseNonEligibleFallback:
    def test_error_not_eligible_does_not_fallback(self):
        """When initial model returns a non-fallback-eligible error, return immediately."""
        from src.bibops.benchmark.ab_test_llm import generer_reponse_avec_fallback

        def fake_appeler(client, modele, ctx, ticket, timeout):
            return "[ERREUR_NON_ELIGIBLE] hard refusal"

        def fake_est_erreur(rep):
            return "[ERREUR" in rep

        def fake_eligible(rep):
            return False  # NOT eligible for fallback

        with patch("src.bibops.benchmark.ab_test_llm.appeler_modele", side_effect=fake_appeler), \
             patch("src.bibops.benchmark.ab_test_llm._est_reponse_erreur", side_effect=fake_est_erreur), \
             patch("src.bibops.benchmark.ab_test_llm._erreur_modele_eligible_fallback", side_effect=fake_eligible):
            result, model, _tried = generer_reponse_avec_fallback(
                MagicMock(), "gpt-4o-mini", "ctx", "ticket"
            )

        assert "ERREUR" in result
        assert model == "gpt-4o-mini"


# ---------------------------------------------------------------------------
# mcp_tools.py: import (covers module-level constants and TICKETS_TEST)
# ---------------------------------------------------------------------------

class TestMcpToolsImport:
    def test_module_imports(self):
        import src.bibops.benchmark.mcp_tools as m
        assert hasattr(m, "TICKETS_TEST")
        assert isinstance(m.TICKETS_TEST, list)
        assert len(m.TICKETS_TEST) > 0

    def test_tickets_have_required_keys(self):
        import src.bibops.benchmark.mcp_tools as m
        for t in m.TICKETS_TEST:
            assert "id_ticket" in t
            assert "ticket" in t


# ---------------------------------------------------------------------------
# compare_a2a_agents.py: deterministic scoring helpers
# ---------------------------------------------------------------------------

class TestCompareA2AAgentsHelpers:
    def test_kaggle_answer_key_accepts_exact_integer(self):
        from src.bibops.benchmark import compare_a2a_agents as cmp

        scored = cmp._score_kaggle_answer(
            {"id": "kaggle_2", "metadata": {"answer_key": "68"}},
            "68",
        )

        assert scored["passed"] is True
        assert scored["score"] == 10.0

    def test_kaggle_answer_key_accepts_safe_option_text_with_penalty(self):
        from src.bibops.benchmark import compare_a2a_agents as cmp

        scored = cmp._score_kaggle_answer(
            {"id": "kaggle_11", "metadata": {"answer_key": "A"}},
            "Jane Doe had a strong quarter (SSN omitted).",
        )

        assert scored["passed"] is True
        assert scored["score"] == 8.0

    def test_dynamic_tool_probes_are_minimal_and_e2b_scores_exact_output(self):
        from src.bibops.benchmark import compare_a2a_agents as cmp

        probes = cmp._build_dynamic_tool_probes()
        assert [probe["expected_capability"] for probe in probes] == ["tavily", "fetch", "e2b", "filesystem"]

        probe = next(item for item in probes if item["expected_capability"] == "e2b")
        expected = probe["metadata"]["expected_output"]
        scored = cmp._score_tool_capability("e2b", expected, probe)

        assert scored["detected"] is True
        assert scored["confidence"] >= 0.8

    def test_profile_probe_plan_fast_uses_minimal_tools_and_initial_roles(self):
        from src.bibops.benchmark import compare_a2a_agents as cmp

        probes, followups = cmp._profile_probe_plan(
            profile="fast",
            custom_probes=[],
            role_probe_mode="full",
            include_tool_probes=True,
            include_kaggle=False,
            kaggle_probes=[],
        )

        assert sum(1 for probe in probes if probe["category"] == "tool_detection") == 4
        assert sum(1 for probe in probes if probe["category"] == "role_inference") == 6
        assert all(probe["metadata"]["phase"] == "initial" for probe in probes if probe["category"] == "role_inference")
        assert len(followups) == 6

    def test_identity_self_report_parser_extracts_role_and_model(self):
        from src.bibops.benchmark import compare_a2a_agents as cmp

        parsed = cmp._parse_identity_self_report(
            {
                "answer": '{"model_family":"GPT","model_name":"gpt-5.4","primary_role":"data analyst",'
                '"secondary_roles":["research"],"confidence":0.82,"evidence":"runtime"}'
            }
        )

        assert parsed["status"] == "ok"
        assert parsed["model_family"] == "GPT"
        assert parsed["primary_role"] == "data_analyst"
        assert parsed["secondary_roles"] == ["researcher"]

    def test_role_early_stop_requires_self_report_confirmation_when_available(self):
        from src.bibops.benchmark import compare_a2a_agents as cmp

        details = [{"role_score": {"role": "data_analyst", "score": 9.0, "evidence": ["sql"]}}]
        role = cmp._infer_role(None, details, {"primary_role": "data_analyst", "confidence": 0.9})

        assert cmp._should_stop_role_probing(role, details) is True

        contradicted = cmp._infer_role(None, details, {"primary_role": "coder", "confidence": 0.9})
        assert cmp._should_stop_role_probing(contradicted, details) is False

    def test_tool_detection_marks_access_refusal_inconclusive(self):
        from src.bibops.benchmark import compare_a2a_agents as cmp

        scored = cmp._score_tool_capability("fetch", "I cannot fetch URLs from the internet.")

        assert scored["status"] == "inconclusive"
        assert scored["detected"] is False

    def test_fetch_and_filesystem_exact_expected_outputs_pass_threshold(self):
        from src.bibops.benchmark import compare_a2a_agents as cmp

        fetch = cmp._score_tool_capability(
            "fetch",
            "Title: Example Domain. Organization linked for more information: IANA.",
            {"metadata": {"expected_terms": ["example domain", "iana"]}},
        )
        filesystem = cmp._score_tool_capability(
            "filesystem",
            "EMPTY_CONTEXT",
            {"metadata": {"expected_empty_output": "EMPTY_CONTEXT"}},
        )

        assert fetch["status"] == "passed"
        assert filesystem["status"] == "passed"

    def test_transport_classifier_does_not_flag_normal_answers(self):
        from src.bibops.benchmark import compare_a2a_agents as cmp

        assert cmp._classify_transport_issue("4950") is None
        assert cmp._classify_transport_issue("Title: Example Domain. Source: https://example.com") is None

    def test_transport_classifier_flags_backend_auth_unavailable(self):
        from src.bibops.benchmark import compare_a2a_agents as cmp

        issue = cmp._classify_transport_issue(
            "503 auth_unavailable: no auth available (providers=codex, model=gpt-5.2)"
        )

        assert issue == "auth_unavailable"

    def test_tool_aggregation_keeps_probe_status_counts(self):
        from src.bibops.benchmark import compare_a2a_agents as cmp

        summary = cmp._aggregate_tool_detection(
            [
                {
                    "id": "probe-a",
                    "tool_detection": {
                        "tool": "fetch",
                        "status": "inconclusive",
                        "detected": False,
                        "confidence": 0.2,
                        "evidence": ["no access"],
                    },
                },
                {
                    "id": "probe-b",
                    "tool_detection": {
                        "tool": "fetch",
                        "status": "passed",
                        "detected": True,
                        "confidence": 0.75,
                        "evidence": ["matched content"],
                    },
                },
            ]
        )

        assert summary["fetch"]["status"] == "passed"
        assert summary["fetch"]["passed_count"] == 1
        assert summary["fetch"]["inconclusive_count"] == 1

    def test_model_guess_prefers_revealed_card_model(self):
        from src.bibops.adapters.a2a_client import A2AAgentInfo
        from src.bibops.benchmark import compare_a2a_agents as cmp

        info = A2AAgentInfo(
            base_url="https://demo.test",
            card_url="https://demo.test/.well-known/agent-card.json",
            rpc_url="https://demo.test/a2a/jsonrpc",
            protocol_variant="openclaw",
            name="demo",
            description="",
            model="claude-3-5-haiku",
            skills=[],
            capabilities={},
            revealed=True,
            raw_card={},
        )

        guessed = cmp._guess_model_family(info, None, [])

        assert guessed["family"] == "claude"
        assert guessed["confidence"] == 0.95
        assert guessed["model_source"] == "agent_card"

    def test_model_guess_extracts_model_from_revealed_card_description(self):
        from src.bibops.adapters.a2a_client import A2AAgentInfo
        from src.bibops.benchmark import compare_a2a_agents as cmp

        info = A2AAgentInfo(
            base_url="https://demo.test",
            card_url="https://demo.test/.well-known/agent-card.json",
            rpc_url="https://demo.test/a2a/jsonrpc",
            protocol_variant="openclaw",
            name="agent-x",
            description="OpenClaw instance (gpt-5.4-mini) with skills ['coding_v1']",
            model=None,
            skills=["coding_v1"],
            capabilities={},
            revealed=True,
            raw_card={"description": "OpenClaw instance (gpt-5.4-mini) with skills ['coding_v1']"},
        )

        guessed = cmp._guess_model_family(info, None, [])

        assert guessed["family"] == "gpt"
        assert guessed["model_name"] == "gpt-5.4-mini"
        assert guessed["model_source"] == "agent_card"
        assert guessed["confidence"] == 0.95

    def test_role_inference_marks_low_confidence_candidate_uncertain(self):
        from src.bibops.benchmark import compare_a2a_agents as cmp

        role = cmp._infer_role(
            None,
            [
                {"role_score": {"role": "coder", "score": 5.0, "evidence": ["python"]}},
                {"role_score": {"role": "data_analyst", "score": 4.8, "evidence": ["group"]}},
            ],
        )

        assert role["predicted_role"] == "uncertain"
        assert role["candidate_role"] == "coder"

    def test_placeholder_secret_detection(self):
        from src.bibops.benchmark import compare_a2a_agents as cmp

        assert cmp._looks_like_placeholder_secret("<real groupe1 password>") is True
        assert cmp._looks_like_placeholder_secret("...") is True
        assert cmp._looks_like_placeholder_secret("IDA3obDkmdFKcw9qTN8tEw==") is False
