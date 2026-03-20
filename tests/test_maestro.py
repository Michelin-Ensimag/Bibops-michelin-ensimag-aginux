"""
tests/test_maestro.py

Tests d'intégration pour la boucle ReAct de src/agents/maestro.py.

Le juge LLM (ollama.chat) est remplacé par GenericFakeChatModel de LangChain :
aucun modèle Ollama n'est nécessaire pour exécuter cette suite.

Architecture du mock :
  ollama.chat(model, messages) → dict{"message": {"content": str}}
  GenericFakeChatModel.invoke  → AIMessage (pop depuis un iterateur de réponses fixes)
  make_fake_ollama_chat()      → factory qui colle les deux couches ensemble

TODO [T1-3a] Regex guillemets simples  – ACTION: outil('ARG') détecté + outil appelé
TODO [T1-3b] Regex guillemets doubles  – ACTION: outil("ARG") détecté + outil appelé
TODO [T1-3c] Hallucination outil       – ACTION: CAFETIERE(...) → erreur renvoyée au LLM,
                                         outil légitime non appelé, pas d'exception
"""
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage

from src.agents.maestro import lancer_agent


# ── Factory : mock d'ollama.chat alimenté par GenericFakeChatModel ────────────

def make_fake_ollama_chat(responses: list[str]):
    """
    Crée un callable compatible avec la signature d'ollama.chat :
        ollama.chat(model: str, messages: list[dict]) -> dict

    Chaque appel consomme la prochaine réponse de `responses` via
    GenericFakeChatModel (qui ignore le contenu des messages d'entrée).

    Note d'implémentation
    ---------------------
    On appelle ``fake_model._generate()`` directement au lieu de ``.invoke()``.
    ``invoke()`` déclenche la chaîne de callbacks LangChain qui accède à des
    attributs legacy du module ``langchain`` (verbose, debug, llm_cache…) supprimés
    dans langchain >= 1.0.  ``_generate()`` est la méthode que GenericFakeChatModel
    override : elle pop simplement le prochain AIMessage de l'itérateur, sans
    passer par aucun callback.  C'est l'approche documentée pour les tests unitaires
    qui ne nécessitent pas de tracing.

    Args:
        responses: Liste ordonnée des contenus texte que le LLM "retournera".

    Returns:
        Callable à passer comme side_effect de patch("ollama.chat").
    """
    ai_messages = [AIMessage(content=r) for r in responses]
    # GenericFakeChatModel pop le prochain AIMessage à chaque appel à _generate()
    fake_model = GenericFakeChatModel(messages=iter(ai_messages))

    def _mock_chat(model: str, messages: list[dict]) -> dict:
        # Appel direct à _generate() pour bypasser le système de callbacks LangChain
        # (compatible langchain-core 0.2.x + langchain 1.x sans shim d'attributs).
        result = fake_model._generate([HumanMessage(content="trigger")])
        content = result.generations[0].message.content
        return {"message": {"content": content}}

    return _mock_chat


# ── Helper : outil-mock compatible avec la boucle ReAct ─────────────────────

def _make_tool_mock(name: str, doc: str, return_value: str) -> MagicMock:
    """
    Crée un MagicMock qui passe les contrôles __name__ / __doc__ de maestro.py.
    La boucle ReAct identifie l'outil par `outil.__name__` et affiche `outil.__doc__`
    dans le prompt système.
    """
    tool = MagicMock(return_value=return_value)
    tool.__name__ = name
    tool.__doc__ = doc
    return tool


# ══════════════════════════════════════════════════════════════════════════════
# Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestMaestroReActLoop:

    # ── TODO [T1-3a] : Regex guillemets simples ───────────────────────────────

    def test_regex_parses_single_quote_action(self):
        """
        TODO [T1-3a] : Valide le fallback regex ACTION: outil('ARG').

        Séquence simulée :
          1. LLM → ACTION: verifier_statut_serveur('VPN')
          2. Outil appelé, résultat injecté dans l'historique
          3. LLM → réponse finale (pas d'ACTION) → fin de boucle
        """
        responses = [
            "ACTION: verifier_statut_serveur('VPN')",
            "Le VPN est HORS LIGNE (Incident 4042).",
        ]
        tool = _make_tool_mock(
            name="verifier_statut_serveur",
            doc="Vérifie l'état d'un serveur.",
            return_value="Statut : Le service VPN est HORS LIGNE (Incident 4042).",
        )

        with patch("ollama.chat", side_effect=make_fake_ollama_chat(responses)):
            result = lancer_agent(
                "L'entreprise est Michelin. Le VPN principal est Cisco.",
                "Mon VPN ne marche plus.",
                outils_disponibles=[tool],
            )

        # L'outil doit avoir été appelé avec exactement l'argument 'VPN'
        tool.assert_called_once_with("VPN")
        assert result is not None

    # ── TODO [T1-3b] : Regex guillemets doubles ───────────────────────────────

    def test_regex_parses_double_quote_action(self):
        """
        TODO [T1-3b] : Valide la regex principale ACTION: outil("ARG").

        Même séquence que le test précédent, mais avec guillemets doubles.
        """
        responses = [
            'ACTION: verifier_statut_serveur("OUTLOOK")',
            "Outlook est EN LIGNE.",
        ]
        tool = _make_tool_mock(
            name="verifier_statut_serveur",
            doc="Vérifie l'état d'un serveur.",
            return_value="Statut : Le service OUTLOOK est EN LIGNE.",
        )

        with patch("ollama.chat", side_effect=make_fake_ollama_chat(responses)):
            result = lancer_agent(
                "Contexte Michelin.",
                "Est-ce qu'Outlook fonctionne ?",
                outils_disponibles=[tool],
            )

        tool.assert_called_once_with("OUTLOOK")
        assert result is not None

    # ── TODO [T1-3c] : Edge case hallucination ────────────────────────────────

    def test_hallucination_unknown_tool_is_handled_gracefully(self):
        """
        TODO [T1-3c] : Edge case – le LLM hallucine un outil inexistant "CAFETIERE".

        Comportements attendus :
          - L'outil légitime (verifier_statut_serveur) n'est PAS appelé.
          - maestro.py retourne une réponse non-vide sans lever d'exception.
          - Le second appel au LLM contient bien le message d'erreur
            "L'outil 'CAFETIERE' n'existe pas" → le LLM peut s'auto-corriger.
        """
        responses = [
            'ACTION: CAFETIERE("café double")',
            "Je ne dispose pas d'un outil pour préparer du café. "
            "Je peux cependant vérifier l'état des serveurs.",
        ]
        real_tool = _make_tool_mock(
            name="verifier_statut_serveur",
            doc="Vérifie l'état d'un serveur.",
            return_value="Statut : VPN HORS LIGNE.",
        )

        with patch("ollama.chat", side_effect=make_fake_ollama_chat(responses)) as mock_ollama:
            result = lancer_agent(
                "Contexte Michelin.",
                "Fais-moi un café s'il te plaît.",
                outils_disponibles=[real_tool],
            )

        # L'outil légitime ne doit jamais avoir été déclenché
        real_tool.assert_not_called()

        # L'agent doit retourner quelque chose sans planter
        assert result is not None and len(result) > 0

        # Le message d'erreur "outil inexistant" doit avoir été renvoyé au LLM
        # lors du deuxième appel (index 1) pour permettre l'auto-correction
        assert mock_ollama.call_count >= 2
        all_calls_str = str(mock_ollama.call_args_list)
        assert "CAFETIERE" in all_calls_str
        assert "n'existe pas" in all_calls_str
