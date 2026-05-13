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

    def test_force_initial_tool_executes_routing_hint_before_llm(self):
        """
        Report benchmarks can force a deterministic first tool call so small
        local models cannot skip the tool/RAG path on obvious IT tickets.
        """
        decisions = [
            AgentDecision(tool=None, final_answer="Le VPN est hors ligne, incident à escalader."),
        ]
        tool = _make_tool_mock(
            name="verifier_statut_serveur",
            doc="Vérifie l'état d'un serveur.",
            return_value="Statut : Le service VPN est HORS LIGNE (Incident 4042).",
        )

        with patch("src.agent.maestro._call_llm", side_effect=make_fake_llm(decisions)):
            result = lancer_agent(
                "Tu es un technicien support IT chez Michelin.",
                "Mon VPN Cisco ne marche plus.",
                outils_disponibles=[tool],
                force_initial_tool=True,
                return_trace=True,
            )

        tool.assert_called_once_with("VPN")
        assert result["trace"]["forced_initial_tool"] is True
        assert result["trace"]["tool_calls"][0]["etape"] == 0

    def test_deterministic_tool_answer_skips_llm_after_forced_tool(self):
        """
        In benchmark mode, the agent can synthesize the final answer directly
        from the tool result so small local models cannot corrupt the KB steps.
        """
        kb_result = """1 solution(s) trouvée(s) :

--- SOLUTION 1 ---
ID : KB-016
Score KB : 42
Problème : Teams : écran noir lors du partage PowerPoint
Catégorie : Collaboration
Priorité : moyenne

DIAGNOSTIC :
  - Vérifier si l'écran noir apparaît en partageant la fenêtre PowerPoint ou l'écran complet

RÉSOLUTION :
  1. Essayer le partage d'écran complet au lieu du partage de fenêtre PowerPoint
  2. Présenter le fichier directement dans Teams avec l'option PowerPoint Live si disponible

ESCALADE : Si l'écran noir persiste : ticket niveau 2 collaboration Microsoft 365
"""
        tool = _make_tool_mock(
            name="chercher_dans_kb",
            doc="Recherche dans la KB.",
            return_value=kb_result,
        )

        with patch("src.agent.maestro._call_llm", side_effect=AssertionError("LLM should not be called")) as mock_llm:
            result = lancer_agent(
                "Tu es un technicien support IT chez Michelin.",
                "Le partage d'écran Teams est noir quand je présente un PowerPoint.",
                outils_disponibles=[tool],
                force_initial_tool=True,
                deterministic_tool_answer=True,
                return_trace=True,
            )

        tool.assert_called_once()
        mock_llm.assert_not_called()
        assert "PowerPoint Live" in result["reponse_finale"]
        assert result["trace"]["outcome"] == "tool_synthesized"

    def test_deterministic_guard_replaces_ungrounded_llm_final_answer(self):
        """
        If the LLM ignores the tool output or drifts to another procedure, the
        guard replaces the final answer with the structured tool synthesis.
        """
        decisions = [
            AgentDecision(tool="chercher_dans_kb", argument="Teams partage écran noir PowerPoint"),
            AgentDecision(tool=None, final_answer="Commencer par vérifier que le fichier .ost n'est pas corrompu."),
        ]
        kb_result = """1 solution(s) trouvée(s) :

--- SOLUTION 1 ---
ID : KB-016
Score KB : 42
Problème : Teams : écran noir lors du partage PowerPoint
Catégorie : Collaboration
Priorité : moyenne

DIAGNOSTIC :
  - Vérifier si l'écran noir apparaît en partageant la fenêtre PowerPoint ou l'écran complet

RÉSOLUTION :
  1. Essayer le partage d'écran complet au lieu du partage de fenêtre PowerPoint
  2. Désactiver l'accélération matérielle dans Teams et Office puis relancer les applications

ESCALADE : Si l'écran noir persiste : ticket niveau 2 collaboration Microsoft 365
"""
        tool = _make_tool_mock(
            name="chercher_dans_kb",
            doc="Recherche dans la KB.",
            return_value=kb_result,
        )

        with patch("src.agent.maestro._call_llm", side_effect=make_fake_llm(decisions)):
            result = lancer_agent(
                "Support IT Michelin.",
                "Le partage d'écran Teams est noir quand je présente un PowerPoint.",
                outils_disponibles=[tool],
                deterministic_tool_answer=True,
                return_trace=True,
            )

        assert "fichier .ost" not in result["reponse_finale"]
        assert "accélération matérielle" in result["reponse_finale"]
        assert result["trace"]["outcome"] == "tool_guardrail_synthesized"

    def test_empty_final_answer_is_repaired(self):
        """
        A blank final answer is not accepted as a completed agent response.
        The loop asks the model for a real answer on the next turn.
        """
        decisions = [
            AgentDecision(tool="verifier_statut_serveur", argument="VPN"),
            AgentDecision(tool=None, final_answer=""),
            AgentDecision(tool=None, final_answer="Le VPN est instable, relancez AnyConnect puis contactez le support N2."),
        ]
        tool = _make_tool_mock(
            name="verifier_statut_serveur",
            doc="Vérifie l'état d'un serveur.",
            return_value="Statut : Le service VPN est EN LIGNE.",
        )

        with patch("src.agent.maestro._call_llm", side_effect=make_fake_llm(decisions)) as mock_llm:
            result = lancer_agent(
                "Support IT Michelin.",
                "Mon VPN ne marche plus.",
                outils_disponibles=[tool],
            )

        assert mock_llm.call_count == 3
        assert "VPN est instable" in result

    def test_empty_final_answer_falls_back_when_no_iteration_left(self):
        decisions = [
            AgentDecision(tool=None, final_answer=""),
        ]
        tool = _make_tool_mock(
            name="verifier_statut_serveur",
            doc="Vérifie l'état d'un serveur.",
            return_value="EN LIGNE.",
        )

        with patch("src.agent.maestro._call_llm", side_effect=make_fake_llm(decisions)):
            result = lancer_agent(
                "Contexte Michelin.",
                "Question sans réponse.",
                outils_disponibles=[tool],
                max_iterations=1,
            )

        assert result
        assert "Je n'ai pas pu" in result

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
