"""
src/bibops/llm_professor/llm_professor.py

Module d'évaluation unifié pour BibOps.

Deux systèmes indépendants coexistent dans ce module :

── PARTIE 1 : Juge LLM (LLMProfessor) ──────────────────────────────────────
  Utilise ChatOpenAI pointé sur le proxy Copilot local (localhost:4141).
  Note les réponses de 0 à 10 avec justification, persiste dans SQLite.
  Méthodes :
    evaluer_reponse()             → évalue une réponse unique (INSERT)
    evaluer_tickets_en_attente()  → batch : tickets sans note → RCA + juge (UPDATE)

── PARTIE 2 : Scoring par règles (EvaluationEngine / EvaluationProcessor) ──
  Scoring pondéré 0–10 sans LLM : erreur (25%), feedback (35%),
  vitesse (20%), tokens (20%). Poids/seuils dans config_evaluation.py.
  Classes :
    EvaluationEngine      → calculate_final_score()
    EvaluationProcessor   → lit tickets_evalues_fake.json, écrit scores JSON
  Utilitaires :
    filter_by_model()     → filtre les résultats par modèle
    compare_models()      → résumé comparatif trié par score moyen
"""

import json
import re
import sqlite3
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from .rca import RCAEngine

try:
    from .config_evaluation import (
        WEIGHTS,
        FEEDBACK_SCORES,
        TIME_THRESHOLDS,
        TOKEN_THRESHOLDS,
        SCORE_MIN,
        SCORE_MAX,
    )
except ImportError:
    from config_evaluation import (
        WEIGHTS,
        FEEDBACK_SCORES,
        TIME_THRESHOLDS,
        TOKEN_THRESHOLDS,
        SCORE_MIN,
        SCORE_MAX,
    )


# ══════════════════════════════════════════════════════════════════════════════
# PARTIE 1 : JUGE LLM
# ══════════════════════════════════════════════════════════════════════════════

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
    Cela permet d'utiliser GitHub Copilot, LiteLLM ou tout proxy OpenAI sans clé cloud.
    """

    def __init__(self, db_path: str, modele_juge: str = "gpt-4o"):
        """
        Args:
            db_path     : Chemin absolu vers bibops.db.
            modele_juge : Nom du modèle exposé par le proxy local (port 4141).
        """
        self.db_path = db_path

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

        Returns:
            Nombre de tickets effectivement évalués (les erreurs individuelles
            n'interrompent pas le batch).
        """
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

        _UPDATE = """
            UPDATE evaluations
            SET    note_juge        = ?,
                   justification_juge = ?
            WHERE  id = ?
        """

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
                    continue

        print(f"\n[LLM Professor] {nb_evalues}/{len(lignes)} ticket(s) évalué(s).")
        return nb_evalues

    # ── Persistance ───────────────────────────────────────────────────────────

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


# ══════════════════════════════════════════════════════════════════════════════
# PARTIE 2 : SCORING PAR RÈGLES
# ══════════════════════════════════════════════════════════════════════════════

class EvaluationEngine:
    """Moteur d'évaluation par règles (sans LLM). Score pondéré 0–10."""

    _STOPWORDS = {
        "le", "la", "les", "de", "du", "des", "un", "une", "et", "est", "en",
        "que", "qui", "dans", "pour", "pas", "sur", "ce", "il", "je", "tu",
        "nous", "vous", "ils", "son", "sa", "ses", "au", "aux", "avec", "ne",
        "se", "ou", "mais", "donc", "car", "ni", "si", "mon", "ma", "mes",
        "ton", "ta", "tes", "par", "plus", "tout", "tres", "bien", "peut",
        "ete", "aussi", "cette", "etre", "avoir", "faire", "comme", "sont",
        "ont", "fait", "dit", "votre", "ces", "cela", "lors", "dont",
        "apres", "avant", "elle", "elles", "leur", "leurs", "meme",
        "puis", "sans", "sous", "chez", "vers", "entre", "encore",
        "the", "is", "are", "was", "to", "of", "and", "in", "for", "on",
        "it", "that", "this", "an", "at", "or", "if", "you", "your",
        "can", "from", "not", "be", "has", "had", "will", "would",
    }

    def __init__(self):
        self.weights = WEIGHTS
        self.feedback_scores = FEEDBACK_SCORES

    def _tokeniser(self, texte: str) -> set:
        """Tokenise un texte en mots significatifs (sans stopwords)."""
        mots = re.findall(r"[a-z0-9]+", texte.lower())
        return {mot for mot in mots if mot not in self._STOPWORDS and len(mot) > 2}

    def _charger_kb(self) -> list:
        """Charge la KB JSON avec cache mémoire."""
        if not hasattr(self, "_kb_cache"):
            kb_path = Path(__file__).resolve().parents[3] / "data" / "knowledge_base" / "knowledge_base.json"
            try:
                with open(kb_path, "r", encoding="utf-8") as f:
                    self._kb_cache = json.load(f).get("knowledge_base", [])
            except (FileNotFoundError, json.JSONDecodeError):
                self._kb_cache = []
        return self._kb_cache

    def _trouver_fiche_kb(self, ticket: str) -> Optional[dict]:
        """Trouve la fiche KB la plus pertinente pour un ticket."""
        kb = self._charger_kb()
        if not kb:
            return None

        ticket_lower = ticket.lower()
        meilleur_score = 0
        meilleure_fiche = None

        for entry in kb:
            score = 0
            for mot in entry.get("mots_cles", []):
                if mot.lower() in ticket_lower:
                    score += 2
            for mot in ticket_lower.split():
                if mot in entry.get("probleme", "").lower():
                    score += 1
            if score > meilleur_score:
                meilleur_score = score
                meilleure_fiche = entry

        return meilleure_fiche if meilleur_score > 0 else None

    def _extraire_termes_reference(self, fiche_kb: dict) -> set:
        """Extrait les termes de référence (mots-clés + problème + étapes)."""
        texte_parts = []
        texte_parts.extend(fiche_kb.get("mots_cles", []))
        texte_parts.append(fiche_kb.get("probleme", ""))

        solution = fiche_kb.get("solution", {})
        texte_parts.extend(solution.get("diagnostic", []))
        texte_parts.extend(solution.get("resolution", []))

        return self._tokeniser(" ".join(texte_parts))

    def score_pertinence(self, reponse: str, ticket: str) -> Dict[str, float]:
        """
        Calcule un F1 textuel entre la réponse et la fiche KB du ticket.

        Retourne:
            {"score", "precision", "recall", "f1"}
        """
        if reponse == "ERREUR" or not reponse.strip():
            return {"score": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0}

        fiche = self._trouver_fiche_kb(ticket)
        if fiche is None:
            # Neutre si la KB ne couvre pas ce ticket.
            return {"score": 5.0, "precision": 0.0, "recall": 0.0, "f1": 0.0}

        termes_kb = self._extraire_termes_reference(fiche)
        termes_reponse = self._tokeniser(reponse)
        if not termes_kb or not termes_reponse:
            return {"score": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0}

        communs = termes_kb & termes_reponse
        precision = len(communs) / len(termes_reponse)
        recall = len(communs) / len(termes_kb)

        if precision + recall == 0:
            return {"score": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0}

        f1 = 2 * (precision * recall) / (precision + recall)
        return {
            "score": round(f1 * 10.0, 2),
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
        }

    def score_erreur(self, reponse: str) -> float:
        """Score 0 si réponse == "ERREUR", 10 sinon."""
        if reponse == "ERREUR":
            return 0.0
        return 10.0

    def score_feedback(self, feedback: str) -> float:
        """Score basé sur le feedback utilisateur (Utile/Partiellement utile/Inutile)."""
        return float(self.feedback_scores.get(feedback, 0))

    def score_vitesse(self, temps_secondes: float) -> float:
        """Score basé sur le temps de réponse (interpolation linéaire par paliers)."""
        if temps_secondes <= TIME_THRESHOLDS["excellent"]:
            return 10.0
        elif temps_secondes <= TIME_THRESHOLDS["good"]:
            return 10.0 - (temps_secondes - TIME_THRESHOLDS["excellent"]) / (
                TIME_THRESHOLDS["good"] - TIME_THRESHOLDS["excellent"]
            ) * 3.0
        elif temps_secondes <= TIME_THRESHOLDS["acceptable"]:
            return 7.0 - (temps_secondes - TIME_THRESHOLDS["good"]) / (
                TIME_THRESHOLDS["acceptable"] - TIME_THRESHOLDS["good"]
            ) * 6.0
        elif temps_secondes <= TIME_THRESHOLDS["slow"]:
            return max(
                0.0,
                1.0
                - (temps_secondes - TIME_THRESHOLDS["acceptable"])
                / (TIME_THRESHOLDS["slow"] - TIME_THRESHOLDS["acceptable"]),
            )
        else:
            return 0.0

    def score_efficacite_tokens(self, nombre_tokens: int) -> float:
        """Score basé sur l'efficacité en termes de tokens (interpolation linéaire par paliers)."""
        if nombre_tokens <= TOKEN_THRESHOLDS["excellent"]:
            return 10.0
        elif nombre_tokens <= TOKEN_THRESHOLDS["good"]:
            return 10.0 - (nombre_tokens - TOKEN_THRESHOLDS["excellent"]) / (
                TOKEN_THRESHOLDS["good"] - TOKEN_THRESHOLDS["excellent"]
            ) * 3.0
        elif nombre_tokens <= TOKEN_THRESHOLDS["acceptable"]:
            return 7.0 - (nombre_tokens - TOKEN_THRESHOLDS["good"]) / (
                TOKEN_THRESHOLDS["acceptable"] - TOKEN_THRESHOLDS["good"]
            ) * 6.0
        elif nombre_tokens <= TOKEN_THRESHOLDS["excessive"]:
            return max(
                0.0,
                1.0
                - (nombre_tokens - TOKEN_THRESHOLDS["acceptable"])
                / (TOKEN_THRESHOLDS["excessive"] - TOKEN_THRESHOLDS["acceptable"]),
            )
        else:
            return 0.0

    def calculate_final_score(
        self,
        reponse: str,
        feedback: str,
        temps_secondes: float,
        nombre_tokens: int,
        ticket: str = "",
    ) -> Dict[str, float]:
        """
        Calcule le score final pondéré.

        Args:
            reponse: Le contenu de la réponse ou "ERREUR"
            feedback: Feedback utilisateur (Utile/Partiellement utile/Inutile)
            temps_secondes: Temps de réponse en secondes
            nombre_tokens: Nombre de tokens utilisés
            ticket: Texte ticket source (utilisé pour le score de pertinence KB)

        Returns:
            Dict contenant les scores individuels + détails F1 + score final
        """
        score_erreur = self.score_erreur(reponse)
        score_feedback = self.score_feedback(feedback)
        score_vitesse = self.score_vitesse(temps_secondes)
        score_efficacite = self.score_efficacite_tokens(nombre_tokens)

        if ticket:
            pertinence_result = self.score_pertinence(reponse, ticket)
            score_pertinence = pertinence_result["score"]
        else:
            pertinence_result = {"score": 5.0, "precision": 0.0, "recall": 0.0, "f1": 0.0}
            score_pertinence = 5.0

        if reponse == "ERREUR":
            final_score = (
                score_erreur * self.weights["erreur_penalty"]
                + score_feedback * self.weights["feedback"] * 0.2
                + score_vitesse * self.weights["vitesse"] * 0.2
                + score_efficacite * self.weights["efficacite_tokens"] * 0.2
                + score_pertinence * self.weights["pertinence"] * 0.2
            ) / (
                self.weights["erreur_penalty"] + 0.2 * (1 - self.weights["erreur_penalty"])
            )
        else:
            final_score = (
                score_erreur * self.weights["erreur_penalty"]
                + score_feedback * self.weights["feedback"]
                + score_vitesse * self.weights["vitesse"]
                + score_efficacite * self.weights["efficacite_tokens"]
                + score_pertinence * self.weights["pertinence"]
            )

        final_score = max(SCORE_MIN, min(SCORE_MAX, final_score))

        return {
            "score_erreur": round(score_erreur, 2),
            "score_feedback": round(score_feedback, 2),
            "score_vitesse": round(score_vitesse, 2),
            "score_efficacite_tokens": round(score_efficacite, 2),
            "score_pertinence": round(score_pertinence, 2),
            "f1_details": {
                "precision": pertinence_result["precision"],
                "recall": pertinence_result["recall"],
                "f1": pertinence_result["f1"],
            },
            "score_final": round(final_score, 2),
        }


class EvaluationProcessor:
    """Lit un fichier de tickets JSON et génère les scores par règles."""

    def __init__(self, input_json_path: str, output_json_path: str):
        """
        Args:
            input_json_path: Chemin vers tickets_evalues_fake.json
            output_json_path: Chemin vers le fichier de résultats avec scores
        """
        self.input_path = Path(input_json_path)
        self.output_path = Path(output_json_path)
        self.engine = EvaluationEngine()

    def evaluate_tickets(self) -> Dict[str, Any]:
        """Lit le fichier de tickets et évalue chacun."""
        with open(self.input_path, "r", encoding="utf-8") as f:
            tickets = json.load(f)

        results = {
            "date_evaluation": datetime.now().isoformat(),
            "total_tickets": len(tickets),
            "tickets_evalues": [],
            "statistiques_par_modele": {},
        }

        for ticket in tickets:
            id_ticket = ticket.get("id_ticket", "unknown")
            modele = ticket.get("modele", "unknown")
            reponse = ticket.get("reponse", "ERREUR")
            feedback = ticket.get("feedback_utilisateur", "Inutile")
            temps = ticket.get("temps_reponse (s)", 0.0)
            tokens = ticket.get("nombre_tokens", 0)
            ticket_texte = (
                ticket.get("ticket")
                or ticket.get("texte_ticket")
                or ticket.get("texte_utilisateur")
                or ""
            )

            scores = self.engine.calculate_final_score(
                reponse,
                feedback,
                temps,
                tokens,
                ticket=ticket_texte,
            )

            result_ticket = {
                "id_ticket": id_ticket,
                "modele": modele,
                "dateheure": ticket.get("dateheure", ""),
                "score_final": scores["score_final"],
                "scores_detailles": {
                    "erreur": scores["score_erreur"],
                    "feedback": scores["score_feedback"],
                    "vitesse": scores["score_vitesse"],
                    "efficacite_tokens": scores["score_efficacite_tokens"],
                    "pertinence": scores["score_pertinence"],
                    "f1_details": scores["f1_details"],
                },
                "donnees_brutes": {
                    "feedback_utilisateur": feedback,
                    "temps_reponse_s": temps,
                    "nombre_tokens": tokens,
                    "reponse_erreur": reponse == "ERREUR",
                },
            }

            results["tickets_evalues"].append(result_ticket)

            if modele not in results["statistiques_par_modele"]:
                results["statistiques_par_modele"][modele] = {"count": 0, "scores": []}
            results["statistiques_par_modele"][modele]["count"] += 1
            results["statistiques_par_modele"][modele]["scores"].append(scores["score_final"])

        for modele, stats in results["statistiques_par_modele"].items():
            scores_list = stats["scores"]
            stats["score_moyen"] = round(statistics.mean(scores_list), 2)
            stats["score_median"] = round(statistics.median(scores_list), 2)
            stats["score_min"] = round(min(scores_list), 2)
            stats["score_max"] = round(max(scores_list), 2)
            stats["score_std_dev"] = round(statistics.stdev(scores_list), 2) if len(scores_list) > 1 else 0.0
            del stats["scores"]

        return results

    def save_results(self, results: Dict[str, Any]) -> None:
        """Sauvegarde les résultats dans le fichier de sortie."""
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"Résultats sauvegardés dans: {self.output_path}")

    def process(self) -> Dict[str, Any]:
        """Processe complètement le fichier d'entrée."""
        print(f"Évaluation des tickets depuis: {self.input_path}")
        results = self.evaluate_tickets()
        self.save_results(results)
        return results


# ── Utilitaires d'analyse ─────────────────────────────────────────────────────

def filter_by_model(results: Dict[str, Any], model_name: str) -> List[Dict]:
    """Filtre les résultats par nom de modèle."""
    return [
        ticket for ticket in results["tickets_evalues"]
        if ticket["modele"] == model_name
    ]


def compare_models(results: Dict[str, Any]) -> Dict[str, Any]:
    """Crée un résumé comparatif des modèles, trié par score moyen décroissant."""
    comparison = {
        modele: {
            "nombre_tickets": stats["count"],
            "score_moyen": stats["score_moyen"],
            "score_median": stats["score_median"],
            "score_range": f"{stats['score_min']}-{stats['score_max']}",
            "score_std_dev": stats["score_std_dev"],
        }
        for modele, stats in results["statistiques_par_modele"].items()
    }
    return dict(sorted(comparison.items(), key=lambda x: x[1]["score_moyen"], reverse=True))


# ── Points d'entrée ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--llm-judge":
        # Test rapide du juge LLM (requiert le proxy Copilot sur localhost:4141)
        import os
        DB_PATH = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../../data/databases/bibops.db")
        )
        prof = LLMProfessor(db_path=DB_PATH)
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
            print(f"\n[OK] Note : {resultat.get('note')}/10")
            print(f"     Justification : {resultat.get('justification')}")
        else:
            print("\n[ERREUR] Aucune réponse du proxy. Vérifiez localhost:4141")

    else:
        # Scoring par règles depuis le dataset fixture.
        DATA_ROOT = Path(__file__).resolve().parents[2] / "data"
        INPUT_FILE = DATA_ROOT / "fixtures" / "benchmark" / "tickets_evalues_fake.json"
        OUTPUT_FILE = DATA_ROOT / "outputs" / "benchmark" / "tickets_evalues_scores.json"

        if not INPUT_FILE.exists():
            fallback_input = Path.cwd() / "data" / "fixtures" / "benchmark" / "tickets_evalues_fake.json"
            if fallback_input.exists():
                INPUT_FILE = fallback_input
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

        processor = EvaluationProcessor(str(INPUT_FILE), str(OUTPUT_FILE))
        results = processor.process()

        print("\n" + "=" * 70)
        print("STATISTIQUES PAR MODÈLE")
        print("=" * 70)
        for modele, stats in compare_models(results).items():
            print(f"\n {modele}")
            print(f"   Tickets: {stats['nombre_tickets']}")
            print(f"   Score moyen: {stats['score_moyen']}/10")
            print(f"   Score médian: {stats['score_median']}/10")
            print(f"   Score min-max: {stats['score_range']}")
            print(f"   Écart-type: {stats['score_std_dev']}")
