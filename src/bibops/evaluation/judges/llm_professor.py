"""
LLM judge (LLMProfessor) — scores agent responses 0-10 via a ChatOpenAI proxy.

Rule-based scoring lives in rule_engine.py.
"""

import sqlite3

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.bibops.evaluation.rca import RCAEngine


class EvaluationResult(BaseModel):
    """Réponse structurée du juge LLM : note sur 10 + justification courte."""
    note: int = Field(description="Note entière de 0 à 10")
    justification: str = Field(description="Explication courte de la note (1-2 phrases)")


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


class LLMProfessor:
    """
    Juge LLM : note les réponses de l'agent BibOps sur 10 et persiste les résultats.

    Le juge est un modèle accessible via un proxy OpenAI-compatible local (port 4141).
    """

    def __init__(self, db_path: str, modele_juge: str = "gpt-4o"):
        self.db_path = db_path
        self.juge_llm = ChatOpenAI(
            base_url="http://localhost:4141/v1",
            api_key="dummy",
            model=modele_juge,
            temperature=0.0,
            model_kwargs={"response_format": {"type": "json_object"}},
        )
        self.parser = JsonOutputParser(pydantic_object=EvaluationResult)
        self.prompt = ChatPromptTemplate.from_template(_PROMPT_TEMPLATE)
        self.chain = self.prompt | self.juge_llm | self.parser

    def evaluer_reponse(
        self,
        ticket_id: int,
        ticket_texte: str,
        reponse_agent: str,
        modele_agent: str,
        temps_reponse: float,
        diagnostic_rca: str = "Non disponible",
    ) -> dict | None:
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
            self._sauvegarder_en_base(ticket_id, modele_agent, reponse_agent, temps_reponse, note, justification)
            return resultat
        except Exception as e:
            print(f"[Erreur LLM Professor] Évaluation échouée : {e}")
            return None

    def evaluer_tickets_en_attente(self) -> int:
        """Évalue en batch toutes les lignes de `evaluations` dont note_juge = 0 ou NULL."""
        _SELECT = """
            SELECT  e.id, e.reponse_ia, e.modele, t.texte_utilisateur
            FROM    evaluations e
            JOIN    tickets t ON e.ticket_id = t.id
            WHERE   e.note_juge = 0 OR e.note_juge IS NULL
        """
        _UPDATE = "UPDATE evaluations SET note_juge = ?, justification_juge = ? WHERE id = ?"

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

            for eval_id, reponse_ia, _modele, texte_ticket in lignes:
                print(f"\n{'─' * 50}")
                print(f"[Ticket eval_id={eval_id}] {texte_ticket[:80]}...")
                diagnostic = rca.analyser_cause_racine(texte_ticket)
                print(f"[RCA] {diagnostic[:120]}...")
                try:
                    resultat = self.chain.invoke({
                        "ticket": texte_ticket,
                        "reponse_agent": reponse_ia,
                        "diagnostic_rca": diagnostic,
                        "format_instructions": self.parser.get_format_instructions(),
                    })
                    note = resultat.get("note", 0)
                    justification = resultat.get("justification", "")
                    print(f" -> Note : {note}/10  |  {justification[:80]}")
                    cursor.execute(_UPDATE, (note, justification, eval_id))
                    conn.commit()
                    nb_evalues += 1
                except Exception as e:
                    print(f"[Erreur] Évaluation échouée pour eval_id={eval_id} : {e}")

        print(f"\n[LLM Professor] {nb_evalues}/{len(lignes)} ticket(s) évalué(s).")
        return nb_evalues

    def _sauvegarder_en_base(self, ticket_id, modele, reponse, temps, note, justification) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.cursor().execute(
                "INSERT INTO evaluations (ticket_id, modele, reponse_ia, temps_reponse_s, note_juge, justification_juge) VALUES (?, ?, ?, ?, ?, ?)",
                (ticket_id, modele, reponse, temps, note, justification),
            )
            conn.commit()
        print("[DB] Évaluation sauvegardée dans la table 'evaluations'.")


if __name__ == "__main__":
    import os
    DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/databases/bibops.db"))
    prof = LLMProfessor(db_path=DB_PATH)
    resultat = prof.evaluer_reponse(
        ticket_id=0,
        ticket_texte="Mon VPN Cisco ne marche plus depuis ce matin.",
        reponse_agent="Le service VPN est HORS LIGNE (Incident 4042). Redémarrez le client Cisco AnyConnect et réessayez.",
        modele_agent="test-proxy",
        temps_reponse=1.0,
        diagnostic_rca="Le VPN Cisco est la cause probable (tunnel sécurisé inaccessible).",
    )
    if resultat:
        print(f"\n[OK] Note : {resultat.get('note')}/10")
        print(f"     Justification : {resultat.get('justification')}")
    else:
        print("\n[ERREUR] Aucune réponse du proxy. Vérifiez localhost:4141")
