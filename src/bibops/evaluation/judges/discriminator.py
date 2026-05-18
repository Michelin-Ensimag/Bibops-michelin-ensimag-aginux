"""
src/bibops/evaluation/judges/discriminator.py

DiscriminatorLLM — évaluateur multi-métriques RAGAS-inspired pour la boucle GAN.

Métriques produites (inspirées de RAGAS) :
  score_faithfulness  : fidélité au RCA / absence d'hallucination        (0-10)
  score_relevance     : pertinence de la réponse par rapport au ticket    (0-10)
  score_context       : qualité du contexte ramené par les outils RAG     (0-10)
  is_perfect          : True uniquement si les 3 scores sont >= 8
  feedback_actionnable: texte guidant l'agent vers la correction

Usage FinOps : evaluer() renvoie aussi {"usage": {"prompt_tokens": X, "completion_tokens": Y}}
extrait directement depuis response_metadata / usage_metadata de l'AIMessage LangChain.

CONTRAINTE PROXY : Le proxy Copilot (localhost:4141) n'accepte que les modèles GPT.
Pour utiliser un modèle Claude, pointez base_url vers un proxy LiteLLM+Anthropic.
"""

from langchain_core.messages import BaseMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


class DiscriminatorOutput(BaseModel):
    """Sortie structurée RAGAS-inspired du Discriminateur."""

    score_faithfulness: int = Field(
        description=(
            "Fidélité SÉMANTIQUE de la réponse au RCA Ground Truth. "
            "0 = la réponse CONTREDIT le RCA ou invente une cause technique fausse, "
            "10 = aucune contradiction avec le RCA. "
            "IMPORTANT : les ajouts raisonnables et cohérents (étapes de bonne pratique IT) "
            "ne sont PAS des hallucinations tant qu'ils ne contredisent pas le RCA."
        )
    )
    score_relevance: int = Field(
        description=(
            "Pertinence de la réponse par rapport au ticket utilisateur. "
            "0 = hors sujet, ne résout pas le problème décrit, "
            "10 = répond directement et complètement au ticket."
        )
    )
    score_context: int = Field(
        description=(
            "Qualité du contexte documentaire utilisé par l'agent (outils RAG). "
            "0 = aucun outil appelé ou résultats inutiles, "
            "10 = documentation exacte et suffisante récupérée."
        )
    )
    is_perfect: bool = Field(
        description="True si la moyenne des 3 scores >= 7. Calculé côté Python, peu importe ta valeur."
    )
    feedback_actionnable: str = Field(
        description=(
            "Si is_perfect=False : guide général sur l'axe à améliorer SANS révéler la solution. "
            "Tu DOIS proscrire toute citation directe d'éléments du RCA (URL, noms de profils, "
            "ports, codes d'incident, noms de procédures Michelin). "
            "Formule en termes pédagogiques : 'creuse la cause racine technique', 'précise "
            "davantage le mécanisme', 'cite la procédure officielle Michelin sans inventer'. "
            "Si is_perfect=True : chaîne vide."
        )
    )


_SYSTEM_PROMPT = """\
Tu es un Discriminateur RAGAS-inspired dans une boucle adversariale.
Tu évalues la réponse d'un agent IA de support IT selon 3 métriques indépendantes.

TON RÔLE : évaluer la qualité SÉMANTIQUE par rapport au RCA, pas la conformité textuelle.
Tu es exigeant mais juste : tu pénalises les contradictions et hors-sujets, pas les ajouts
pédagogiques cohérents avec une bonne pratique IT.

━━━ MÉTRIQUE 1 — FAITHFULNESS (Fidélité sémantique) ━━━
Question : La réponse CONTREDIT-elle le RCA Ground Truth ou invente-t-elle une cause fausse ?
- 8-10 : Aucune contradiction. La cause racine identifiée correspond au RCA, même si la
         formulation diffère. Des étapes de bonne pratique IT ajoutées sont OK.
- 5-7  : 1-2 affirmations en désaccord léger avec le RCA, ou détails techniques imprécis.
- 0-4  : Contradiction directe (cause inventée, URL/procédure fausse présentée comme vraie).

IMPORTANT : "L'agent a ajouté X qui n'est pas dans le RCA" n'est PAS une hallucination si X
est une bonne pratique IT raisonnable. Ne pénalise que ce qui CONTREDIT le RCA.

━━━ MÉTRIQUE 2 — RELEVANCE (Pertinence) ━━━
Question : La réponse adresse-t-elle le problème du ticket ?
- 8-10 : Identifie correctement le type de problème et propose une solution actionnable.
- 5-7  : Réponse partiellement adaptée mais manque de spécificité.
- 0-4  : Hors sujet, refuse d'aider, ou répond à un autre problème.

━━━ MÉTRIQUE 3 — CONTEXT (Qualité du contexte) ━━━
Question : Le contenu mobilisé (outils RAG ou raisonnement zero-shot) est-il pertinent ?
- 8-10 : Le contexte mobilisé couvre la cause racine et les étapes de résolution.
- 5-7  : Contexte partiellement aligné.
- 0-4  : Contexte absent, incorrect, ou totalement hors sujet.

━━━ CONDITION is_perfect ━━━
Calculée côté Python (moyenne >= 7). Mets ce que tu veux dans le JSON, on l'écrase.

━━━ FEEDBACK ACTIONNABLE — RÈGLES STRICTES ━━━
Tu ne dois JAMAIS révéler la solution exacte du RCA. INTERDIT de citer :
  - Les URLs, noms de profils, ports, codes d'incident, noms de procédures Michelin
  - Les étapes précises listées dans le RCA
  - Les noms de profils VPN, certificats, services internes

Formule un feedback PÉDAGOGIQUE et GÉNÉRAL, comme un professeur qui guide sans donner
la réponse. Exemples :
  - Faithfulness bas → "Ta réponse contredit la cause racine attendue : revois le type
    d'incident en jeu (réseau / authentification / certificat / quota) avant de proposer
    une solution."
  - Relevance bas    → "Ta réponse reste générique. Identifie le mécanisme technique
    spécifique évoqué par le ticket (code d'erreur, contexte géographique, application
    précise) et adresse-le."
  - Context bas      → "Le contexte que tu mobilises n'est pas spécifique au RCA. Cherche
    la procédure officielle Michelin associée à ce type d'incident."

Le feedback doit faire **2 phrases maximum** et ne contenir **aucun nom propre Michelin**.

Renvoie UNIQUEMENT un JSON valide avec exactement ces 5 clés :
  "score_faithfulness"   — entier 0 à 10
  "score_relevance"      — entier 0 à 10
  "score_context"        — entier 0 à 10
  "is_perfect"           — booléen (sera recalculé)
  "feedback_actionnable" — string (2 phrases max, sans citation du RCA)

{format_instructions}
"""

_HUMAN_PROMPT = """\
TICKET UTILISATEUR : {ticket}

RCA GROUND TRUTH   : {rca_ground_truth}

RÉPONSE DE L'AGENT : {reponse_agent}
"""


def _extract_usage(ai_message: BaseMessage) -> dict:
    """Extrait (prompt_tokens, completion_tokens). Cascade: usage_metadata (LC >=0.2)
    → response_metadata.token_usage (OpenAI natif) → zéros (proxy Copilot)."""
    um = getattr(ai_message, "usage_metadata", None) or {}
    if um:
        return {"prompt_tokens": int(um.get("input_tokens", 0)),
                "completion_tokens": int(um.get("output_tokens", 0))}
    tu = (getattr(ai_message, "response_metadata", None) or {}).get("token_usage", {})
    return {"prompt_tokens": int(tu.get("prompt_tokens", 0)),
            "completion_tokens": int(tu.get("completion_tokens", 0))}


class DiscriminatorLLM:
    """
    Évaluateur multi-métriques RAGAS-inspired pour la boucle adversariale.

    evaluer() renvoie les 5 champs RAGAS + un champ "usage" pour le tracking FinOps :
        {
            "score_faithfulness": 9, "score_relevance": 7, "score_context": 4,
            "is_perfect": False,
            "feedback_actionnable": "Ton score_context est très bas...",
            "usage": {"prompt_tokens": 850, "completion_tokens": 120}
        }
    """

    SEUIL_MOYENNE: float = 7.0  # is_perfect ssi (F + R + C) / 3 >= SEUIL_MOYENNE

    def __init__(
        self,
        modele: str = "gpt-5.2",
        base_url: str = "http://localhost:4141/v1",
        api_key: str = "copilot",
        temperature: float = 1.0,
    ):
        self._llm = ChatOpenAI(
            base_url=base_url,
            api_key=api_key,
            model=modele,
            temperature=temperature,
            model_kwargs={"response_format": {"type": "json_object"}},
        )
        self._parser = JsonOutputParser(pydantic_object=DiscriminatorOutput)
        self._prompt = ChatPromptTemplate.from_messages([
            ("system", _SYSTEM_PROMPT),
            ("human", _HUMAN_PROMPT),
        ])
        # Pipeline en deux étapes : prompt → llm (pour récupérer l'AIMessage brut)
        # puis parser séparé — nécessaire pour intercepter response_metadata.
        self._prompt_llm = self._prompt | self._llm

    def evaluer(self, ticket: str, reponse_agent: str, rca_ground_truth: str) -> dict:
        """
        Évalue la réponse de l'agent selon 3 métriques RAGAS-inspired.

        La chaîne est volontairement cassée en deux étapes pour capturer
        les métadonnées de tokens AVANT que le JsonOutputParser ne les efface.

        Returns:
            dict avec les clés ``score_faithfulness``, ``score_relevance``,
            ``score_context``, ``is_perfect``, ``feedback_actionnable``, ``usage``.
        """
        inputs = {
            "ticket": ticket,
            "reponse_agent": reponse_agent,
            "rca_ground_truth": rca_ground_truth,
            "format_instructions": self._parser.get_format_instructions(),
        }

        # Chaîne cassée en 2 étapes pour capturer les métadonnées de tokens
        # AVANT que le JsonOutputParser ne les efface.
        ai_message = self._prompt_llm.invoke(inputs)
        usage = _extract_usage(ai_message)
        resultat = self._parser.parse(ai_message.content)

        # Enforce is_perfect côté Python — ne pas déléguer ça au LLM
        scores = {k: int(resultat.get(k, 0)) for k in
                  ("score_faithfulness", "score_relevance", "score_context")}
        resultat.update(scores)
        resultat["is_perfect"] = sum(scores.values()) / 3 >= self.SEUIL_MOYENNE
        if resultat["is_perfect"]:
            resultat["feedback_actionnable"] = ""
        resultat["usage"] = usage
        return resultat
