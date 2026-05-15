"""
LLM judge (LLMProfessor) — scores IT support agent responses 0-10.

Uses LLMJudge internally (raw OpenAI client, no LangChain dependency).
Rule-based scoring lives in rule_engine.py.
"""
from __future__ import annotations

import sqlite3

from openai import OpenAI as _OpenAI

from src.bibops.evaluation.judges.llm_judge import LLMJudge
from src.bibops.evaluation.rca import RCAEngine
from src.common.config import DEFAULT_JUDGE_MODEL
from src.common.llm_clients import get_copilot_client

_CRITERION = """\
Tu es un expert en support IT (BibOps LLM Professor).
Ta mission est d'évaluer la réponse d'un agent IA à un ticket utilisateur.

Analyse Technique RCA disponible : {diagnostic_rca}

Critères d'évaluation :
1. Pertinence   : La réponse adresse-t-elle le problème exact décrit dans le ticket ?
2. Clarté       : Les instructions sont-elles faciles à suivre pour un utilisateur non-technicien ?
3. Complétude   : Manque-t-il des étapes cruciales pour résoudre le problème ?

Renvoie UNIQUEMENT un objet JSON valide avec :
  - "score"         : entier de 0 à 10
  - "justification" : explication courte (1-2 phrases)\
"""


class LLMProfessor:
    """
    Juge LLM : note les réponses de l'agent BibOps sur 10 et persiste les résultats.

    Wraps LLMJudge with an IT-support-specific prompt, RCA context, and SQLite persistence.
    """

    def __init__(self, db_path: str, modele_juge: str = DEFAULT_JUDGE_MODEL, client: _OpenAI | None = None):
        self.db_path = db_path
        self._judge = LLMJudge(
            client=client if client is not None else get_copilot_client(),
            model=modele_juge,
        )

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
        criterion = _CRITERION.format(diagnostic_rca=diagnostic_rca)
        verdict = self._judge.score(criterion=criterion, question=ticket_texte, answer=reponse_agent)
        if not verdict.ok:
            print(f"[Erreur LLM Professor] Évaluation échouée : {verdict.justification}")
            return None
        note = round(verdict.score)
        justification = verdict.justification
        print(f" -> Note        : {note}/10")
        print(f" -> Justification : {justification}")
        self._sauvegarder_en_base(ticket_id, modele_agent, reponse_agent, temps_reponse, note, justification)
        return {"note": note, "justification": justification}

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
                criterion = _CRITERION.format(diagnostic_rca=diagnostic)
                verdict = self._judge.score(criterion=criterion, question=texte_ticket, answer=reponse_ia)
                if not verdict.ok:
                    print(f"[Erreur] Évaluation échouée pour eval_id={eval_id} : {verdict.justification}")
                    continue
                note = round(verdict.score)
                justification = verdict.justification
                print(f" -> Note : {note}/10  |  {justification[:80]}")
                cursor.execute(_UPDATE, (note, justification, eval_id))
                conn.commit()
                nb_evalues += 1

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


