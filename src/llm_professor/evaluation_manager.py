"""
src/llm_professor/evaluation_manager.py

LLM Professor : évalue les réponses de l'agent BibOps via un juge LLM.

Juge   : ChatOpenAI pointé sur le proxy local OpenAI-compatible (localhost:4141).
         Compatible GitHub Copilot proxy, LiteLLM, etc.
Scale  : note de 0 à 10.

Classes :
  EvaluationResult          – Schéma Pydantic de la réponse du juge (note + justification).
  LLMProfessor              – Juge LLM avec persistance SQLite.

Méthodes publiques :
  evaluer_reponse()             → évalue une réponse unique (INSERT dans evaluations).
  evaluer_tickets_en_attente()  → batch : note_juge = 0 ou NULL → appel RCA + juge (UPDATE).

TODO [T2-0] Import RCAEngine pour enrichir les évaluations avec un diagnostic technique
TODO [T2-1] evaluer_reponse     – évalue + persiste une réponse d'agent (INSERT)
TODO [T2-2] evaluer_tickets_en_attente – JOIN evaluations/tickets, RCA, LLM, UPDATE
"""
import sqlite3

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

# TODO [T2-0]: RCAEngine utilisé dans evaluer_tickets_en_attente pour le diagnostic
from src.llm_professor.rca_engine import RCAEngine


# ── Schéma de sortie attendu du juge ─────────────────────────────────────────

class EvaluationResult(BaseModel):
    """Réponse structurée du juge LLM : note sur 10 + justification courte."""

    note: int = Field(description="Note entière de 0 à 10")
    justification: str = Field(description="Explication courte de la note (1-2 phrases)")


# ── Prompt d'évaluation ───────────────────────────────────────────────────────

_PROMPT_TEMPLATE = """\
Tu es un expert en support IT (BibOps LLM Professor).
Ta mission est d'évaluer la réponse d'un agent IA à un ticket utilisateur.

Analyse Technique RCA disponible : {diagnostic_rca}

Critères d'évaluation :
1. Pertinence   : La réponse adresse-t-elle le problème exact décrit dans le ticket ?
2. Clarté       : Les instructions sont-elles faciles à suivre pour un utilisateur non-technicien ?
3. Complétude   : Manque-t-il des étapes cruciales pour résoudre le problème ?

Renvoie UNIQUEMENT un objet JSON valide avec :
  - "note"          : entier de 0 à 10
  - "justification" : explication courte (1-2 phrases)

{format_instructions}

Ticket Utilisateur  : {ticket}
Réponse de l'Agent  : {reponse_agent}\
"""


# ── Classe principale ─────────────────────────────────────────────────────────

class LLMProfessor:
    """
    Juge LLM : note les réponses de l'agent BibOps sur 10 et persiste les résultats.

    Le juge est un modèle accessible via un proxy OpenAI-compatible local (port 4141).
    Cela permet d'utiliser GitHub Copilot, LiteLLM ou tout proxy OpenAI sans clé cloud.
    """

    def __init__(self, db_path: str, modele_juge: str = "gpt-4o"):
        """
        Args:
            db_path     : Chemin absolu vers bibops.db.
            modele_juge : Nom du modèle exposé par le proxy local (port 4141).
        """
        self.db_path = db_path

        # TODO [T2-1]: Proxy OpenAI-compatible local – pas de clé cloud nécessaire
        self.juge_llm = ChatOpenAI(
            base_url="http://localhost:4141/v1",
            api_key="dummy",  # le proxy local n'exige pas de clé réelle
            model=modele_juge,
            temperature=0.0,
            model_kwargs={"response_format": {"type": "json_object"}},
        )

        self.parser = JsonOutputParser(pydantic_object=EvaluationResult)
        self.prompt = ChatPromptTemplate.from_template(_PROMPT_TEMPLATE)
        self.chain = self.prompt | self.juge_llm | self.parser

    # ── Évaluation d'une réponse unique ──────────────────────────────────────

    def evaluer_reponse(
        self,
        ticket_id: int,
        ticket_texte: str,
        reponse_agent: str,
        modele_agent: str,
        temps_reponse: float,
        diagnostic_rca: str = "Non disponible",
    ) -> dict | None:
        """
        Soumet une réponse d'agent au juge LLM et insère le résultat dans SQLite.

        TODO [T2-1]: Appel synchrone au juge avec diagnostic RCA optionnel.

        Args:
            ticket_id      : Clé étrangère vers la table tickets.
            ticket_texte   : Texte du ticket utilisateur.
            reponse_agent  : Réponse générée par l'agent BibOps.
            modele_agent   : Nom du modèle agent utilisé (ex: "phi3:latest").
            temps_reponse  : Temps de réponse en secondes.
            diagnostic_rca : Diagnostic RCA optionnel pour enrichir l'évaluation.

        Returns:
            Dict {"note": int, "justification": str} ou None si le juge échoue.
        """
        print(f"\n[LLM Professor] Évaluation de la réponse de {modele_agent}...")

        try:
            resultat = self.chain.invoke({
                "ticket": ticket_texte,
                "reponse_agent": reponse_agent,
                "diagnostic_rca": diagnostic_rca,
                "format_instructions": self.parser.get_format_instructions(),
            })

            note = resultat.get("note")
            justification = resultat.get("justification")

            print(f" -> Note        : {note}/10")
            print(f" -> Justification : {justification}")

            self._sauvegarder_en_base(
                ticket_id, modele_agent, reponse_agent, temps_reponse, note, justification
            )
            return resultat

        except Exception as e:
            print(f"[Erreur LLM Professor] Évaluation échouée : {e}")
            return None

    # ── Traitement batch : évaluations en attente ─────────────────────────────

    def evaluer_tickets_en_attente(self) -> int:
        """
        Évalue en batch toutes les lignes de `evaluations` dont note_juge = 0 ou NULL.

        Pipeline pour chaque ticket :
          1. JOIN evaluations ⨝ tickets pour récupérer le texte du ticket.
          2. Appel RCAEngine → diagnostic technique (cause racine).
          3. Envoi au juge LLM : ticket + réponse agent + diagnostic RCA.
          4. UPDATE evaluations SET note_juge, justification_juge WHERE id = ?.

        TODO [T2-2a]: SELECT JOIN – tickets en attente (note_juge = 0 ou NULL)
        TODO [T2-2b]: RCAEngine   – diagnostic technique pour chaque ticket
        TODO [T2-2c]: Juge LLM    – invocation chaîne LangChain
        TODO [T2-2d]: UPDATE SQL  – persistance de la note et de la justification

        Returns:
            Nombre de tickets effectivement évalués (les erreurs individuelles
            n'interrompent pas le batch).
        """
        # TODO [T2-2a]: Récupère les évaluations sans note via un JOIN
        _SELECT = """
            SELECT  e.id,
                    e.reponse_ia,
                    e.modele,
                    t.texte_utilisateur
            FROM    evaluations e
            JOIN    tickets t ON e.ticket_id = t.id
            WHERE   e.note_juge = 0
               OR   e.note_juge IS NULL
        """

        # TODO [T2-2d]: Met à jour la note et la justification pour un eval_id donné
        _UPDATE = """
            UPDATE evaluations
            SET    note_juge        = ?,
                   justification_juge = ?
            WHERE  id = ?
        """

        # TODO [T2-2b]: RCAEngine instancié une seule fois pour tout le batch
        rca = RCAEngine()
        nb_evalues = 0

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(_SELECT)
            lignes = cursor.fetchall()

            if not lignes:
                print("[LLM Professor] Aucun ticket en attente d'évaluation.")
                return 0

            print(f"[LLM Professor] {len(lignes)} ticket(s) en attente.")

            for eval_id, reponse_ia, modele, texte_ticket in lignes:
                print(f"\n{'─' * 50}")
                print(f"[Ticket eval_id={eval_id}] {texte_ticket[:80]}...")

                # TODO [T2-2b]: Diagnostic RCA – cause racine du ticket
                diagnostic = rca.analyser_cause_racine(texte_ticket)
                print(f"[RCA] {diagnostic[:120]}...")

                try:
                    # TODO [T2-2c]: Invocation du juge LLM avec le contexte enrichi
                    resultat = self.chain.invoke({
                        "ticket": texte_ticket,
                        "reponse_agent": reponse_ia,
                        "diagnostic_rca": diagnostic,
                        "format_instructions": self.parser.get_format_instructions(),
                    })

                    note = resultat.get("note", 0)
                    justification = resultat.get("justification", "")

                    print(f" -> Note : {note}/10  |  {justification[:80]}")

                    # TODO [T2-2d]: Persistance de la note et de la justification
                    cursor.execute(_UPDATE, (note, justification, eval_id))
                    conn.commit()
                    nb_evalues += 1

                except Exception as e:
                    print(f"[Erreur] Évaluation échouée pour eval_id={eval_id} : {e}")
                    continue  # les autres tickets continuent d'être traités

        print(f"\n[LLM Professor] {nb_evalues}/{len(lignes)} ticket(s) évalué(s).")
        return nb_evalues

    # ── Persistance (chemin INSERT depuis evaluer_reponse) ────────────────────

    def _sauvegarder_en_base(
        self,
        ticket_id: int,
        modele: str,
        reponse: str,
        temps: float,
        note: int,
        justification: str,
    ) -> None:
        """Insère une nouvelle ligne d'évaluation dans la table `evaluations`."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO evaluations
                    (ticket_id, modele, reponse_ia, temps_reponse_s, note_juge, justification_juge)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (ticket_id, modele, reponse, temps, note, justification),
            )
            conn.commit()
        print("[DB] Évaluation sauvegardée dans la table 'evaluations'.")


# ── Point d'entrée : test rapide du proxy Copilot ────────────────────────────

if __name__ == "__main__":
    import os

    print("=" * 55)
    print("  TEST DE CONNEXION AU PROXY COPILOT (localhost:4141)")
    print("=" * 55)

    DB_PATH = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../data/databases/bibops.db")
    )

    prof = LLMProfessor(db_path=DB_PATH)

    print("\n[1] Envoi d'un ticket de test au juge LLM...")
    resultat = prof.evaluer_reponse(
        ticket_id=0,
        ticket_texte="Mon VPN Cisco ne marche plus depuis ce matin.",
        reponse_agent="Le service VPN est HORS LIGNE (Incident 4042). "
                      "Redémarrez le client Cisco AnyConnect et réessayez.",
        modele_agent="test-proxy",
        temps_reponse=1.0,
        diagnostic_rca="Le VPN Cisco est la cause probable (tunnel sécurisé inaccessible).",
    )

    if resultat:
        print("\n[OK] Proxy opérationnel.")
        print(f"     Note        : {resultat.get('note')}/10")
        print(f"     Justification : {resultat.get('justification')}")
    else:
        print("\n[ERREUR] Aucune réponse du proxy.")
        print("         Vérifiez que le proxy tourne sur http://localhost:4141")
