"""
tests/test_maestro.py

Tests for the ReAct loop in src/agent/maestro.py.

The LLM call (_call_llm) is patched to return AgentDecision objects directly —
no Ollama or network connection required.
"""
from unittest.mock import MagicMock, patch

from src.agent.maestro import AgentDecision, lancer_agent

# ── Mock factory ──────────────────────────────────────────────────────────────

def make_fake_llm(decisions: list[AgentDecision]):
    """
    Returns a side_effect callable that feeds AgentDecision objects one by one
    to each _call_llm invocation, regardless of the arguments passed.
    """
    it = iter(decisions)

    def _mock(client, model, messages, response_model):
        return next(it)

    return _mock


# ── Tool mock helper ──────────────────────────────────────────────────────────

def _make_tool_mock(name: str, doc: str, return_value: str) -> MagicMock:
    tool = MagicMock(return_value=return_value)
    tool.__name__ = name
    tool.__doc__ = doc
    return tool


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestMaestroReActLoop:

    def test_tool_call_then_final_answer(self):
        """
        LLM requests a tool on turn 1, then returns a final answer on turn 2.
        The tool must be called with exactly the argument the LLM provided.
        """
        decisions = [
            AgentDecision(tool="verifier_statut_serveur", argument="VPN"),
            AgentDecision(tool=None, final_answer="Le VPN est HORS LIGNE (Incident 4042)."),
        ]
        tool = _make_tool_mock(
            name="verifier_statut_serveur",
            doc="Vérifie l'état d'un serveur.",
            return_value="Statut : Le service VPN est HORS LIGNE (Incident 4042).",
        )

        with patch("src.agent.maestro._call_llm", side_effect=make_fake_llm(decisions)):
            result = lancer_agent(
                "L'entreprise est Michelin. Le VPN principal est Cisco.",
                "Mon VPN ne marche plus.",
                outils_disponibles=[tool],
            )

        tool.assert_called_once_with("VPN")
        assert result is not None

    def test_direct_final_answer_no_tool(self):
        """
        LLM returns a final answer immediately without calling any tool.
        """
        decisions = [
            AgentDecision(tool=None, final_answer="Outlook est EN LIGNE."),
        ]
        tool = _make_tool_mock(
            name="verifier_statut_serveur",
            doc="Vérifie l'état d'un serveur.",
            return_value="EN LIGNE.",
        )

        with patch("src.agent.maestro._call_llm", side_effect=make_fake_llm(decisions)):
            result = lancer_agent(
                "Contexte Michelin.",
                "Est-ce qu'Outlook fonctionne ?",
                outils_disponibles=[tool],
            )

        tool.assert_not_called()
        assert result is not None

    def test_hallucination_unknown_tool_is_handled_gracefully(self):
        """
        The LLM hallucinates a tool name ("CAFETIERE") that doesn't exist.

        Expected behaviour:
          - The real tool (verifier_statut_serveur) is NOT called.
          - lancer_agent returns a non-empty result without raising.
          - The second _call_llm call receives a message containing the error
            "n'existe pas", giving the LLM a chance to self-correct.
        """
        decisions = [
            AgentDecision(tool="CAFETIERE", argument="café double"),
            AgentDecision(tool=None, final_answer="Je ne peux pas préparer du café."),
        ]
        real_tool = _make_tool_mock(
            name="verifier_statut_serveur",
            doc="Vérifie l'état d'un serveur.",
            return_value="Statut : VPN HORS LIGNE.",
        )

        with patch("src.agent.maestro._call_llm", side_effect=make_fake_llm(decisions)) as mock_llm:
            result = lancer_agent(
                "Contexte Michelin.",
                "Fais-moi un café s'il te plaît.",
                outils_disponibles=[real_tool],
            )

        real_tool.assert_not_called()
        assert result is not None and len(result) > 0

        # Second call must carry the "n'existe pas" error in its messages
        assert mock_llm.call_count >= 2
        second_call_messages = str(mock_llm.call_args_list[1])
        assert "n'existe pas" in second_call_messages
