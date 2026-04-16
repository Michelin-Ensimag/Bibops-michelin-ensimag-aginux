"""
src/llm_professor/discriminator.py

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
            "Fidélité de la réponse au RCA Ground Truth. "
            "0 = hallucination totale (informations inventées), "
            "10 = strictement fidèle, aucune information fabriquée."
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
        description="True uniquement si score_faithfulness >= 8 ET score_relevance >= 8 ET score_context >= 8."
    )
    feedback_actionnable: str = Field(
        description=(
            "Si is_perfect=False : explique précisément quelle métrique est la plus faible "
            "et ce que l'agent doit corriger (ex : 'Ton score_context est bas : rappelle "
            "l'outil avec un meilleur mot-clé'). Si is_perfect=True : chaîne vide."
        )
    )


_SYSTEM_PROMPT = """\
Tu es un Discriminateur adversarial RAGAS-inspired dans une boucle d'entraînement GAN.
Tu évalues la réponse d'un agent IA de support IT selon 3 métriques indépendantes.

TON RÔLE : débusquer les hallucinations, les hors-sujets, et les mauvais appels d'outils.
Tu n'es PAS bienveillant. Tu es rigoureux, précis, exigeant.

━━━ MÉTRIQUE 1 — FAITHFULNESS (Fidélité) ━━━
Question : La réponse contient-elle UNIQUEMENT des informations présentes dans le RCA Ground Truth ?
- 8-10 : Toutes les affirmations sont tracées au RCA. Zéro invention.
- 5-7  : Quelques éléments corrects mais 1-2 informations non présentes dans le RCA.
- 0-4  : L'agent a inventé des procédures, ports, profils ou causes absents du RCA.

━━━ MÉTRIQUE 2 — RELEVANCE (Pertinence) ━━━
Question : La réponse répond-elle directement au problème décrit dans le ticket ?
- 8-10 : Adresse la cause racine exacte du ticket, solution actionnable, contexte utilisé.
- 5-7  : Réponse générique ou partiellement adaptée au ticket.
- 0-4  : Hors sujet, répond à un autre problème, ou refuse d'aider.

━━━ MÉTRIQUE 3 — CONTEXT (Qualité du contexte RAG) ━━━
Question : L'agent a-t-il utilisé ses outils pour ramener la bonne documentation ?
- 8-10 : L'outil appelé avec les bons mots-clés a retourné la documentation pertinente.
- 5-7  : Outil appelé mais résultats partiels ou mots-clés sous-optimaux.
- 0-4  : Aucun outil appelé, mauvais outil utilisé, ou résultats totalement hors sujet.

━━━ CONDITION is_perfect ━━━
is_perfect = True UNIQUEMENT si score_faithfulness >= 8 ET score_relevance >= 8 ET score_context >= 8.

━━━ FEEDBACK ACTIONNABLE ━━━
Si is_perfect=False, identifie la métrique la plus faible et donne une instruction précise :
- Faithfulness bas → "Tu as halluciné [X]. Colle-toi strictement aux résultats des outils."
- Relevance bas    → "Ta réponse ne traite pas [problème exact]. Adresse directement [cause]."
- Context bas      → "Ton score context est bas. Rappelle l'outil avec le mot-clé [X]."

Renvoie UNIQUEMENT un JSON valide avec exactement ces 5 clés :
  "score_faithfulness"   — entier 0 à 10
  "score_relevance"      — entier 0 à 10
  "score_context"        — entier 0 à 10
  "is_perfect"           — booléen
  "feedback_actionnable" — string (vide si is_perfect=true)

{format_instructions}
"""

_HUMAN_PROMPT = """\
TICKET UTILISATEUR : {ticket}

RCA GROUND TRUTH   : {rca_ground_truth}

RÉPONSE DE L'AGENT : {reponse_agent}
"""


def _extract_usage(ai_message: BaseMessage) -> dict:
    """
    Extrait les compteurs de tokens depuis les métadonnées de l'AIMessage LangChain.

    Stratégie de fallback (du plus au moins récent) :
      1. usage_metadata   → format unifié LangChain >= 0.2
                            {"input_tokens": X, "output_tokens": Y, "total_tokens": Z}
      2. response_metadata → format natif OpenAI via LangChain
                            {"token_usage": {"prompt_tokens": X, "completion_tokens": Y}}
      3. Zéros             → proxy ne renvoie pas de métadonnées (Copilot proxy limité)
    """
    # Priorité 1 : usage_metadata (LangChain >= 0.2)
    usage_meta = getattr(ai_message, "usage_metadata", None)
    if usage_meta:
        return {
            "prompt_tokens": int(usage_meta.get("input_tokens", 0)),
            "completion_tokens": int(usage_meta.get("output_tokens", 0)),
        }

    # Priorité 2 : response_metadata (format OpenAI natif)
    resp_meta = getattr(ai_message, "response_metadata", None)
    if resp_meta:
        token_usage = resp_meta.get("token_usage", {})
        return {
            "prompt_tokens": int(token_usage.get("prompt_tokens", 0)),
            "completion_tokens": int(token_usage.get("completion_tokens", 0)),
        }

    # Fallback : proxy ne fournit pas de métadonnées
    return {"prompt_tokens": 0, "completion_tokens": 0}


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

    SEUIL_PARFAIT: int = 8  # chaque métrique doit atteindre ce seuil

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

        # Étape 1 : appel LLM → AIMessage avec response_metadata intact
        ai_message = self._prompt_llm.invoke(inputs)

        # Étape 2 : extraction des tokens AVANT le parsing
        usage = _extract_usage(ai_message)

        # Étape 3 : parsing du JSON depuis le contenu texte
        resultat = self._parser.parse(ai_message.content)

        # Enforce is_perfect côté Python — ne pas déléguer ça au LLM
        sf = int(resultat.get("score_faithfulness", 0))
        sr = int(resultat.get("score_relevance", 0))
        sc = int(resultat.get("score_context", 0))
        is_perfect = (
            sf >= self.SEUIL_PARFAIT
            and sr >= self.SEUIL_PARFAIT
            and sc >= self.SEUIL_PARFAIT
        )

        resultat["score_faithfulness"] = sf
        resultat["score_relevance"] = sr
        resultat["score_context"] = sc
        resultat["is_perfect"] = is_perfect
        if is_perfect:
            resultat["feedback_actionnable"] = ""

        # Injection des métadonnées FinOps
        resultat["usage"] = usage

        return resultat
