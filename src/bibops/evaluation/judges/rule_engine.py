"""
Rule-based scoring engine — no LLM required.

EvaluationEngine   : weighted 0-10 score from 5 dimensions (error, feedback,
                     speed, token efficiency, KB relevance via F1).
EvaluationProcessor: reads a tickets JSON, scores every entry, writes results.
filter_by_model / compare_models : analysis utilities.
"""

import json
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any

from src.bibops.evaluation.config import (
    FEEDBACK_SCORES,
    SCORE_MAX,
    SCORE_MIN,
    TIME_THRESHOLDS,
    TOKEN_THRESHOLDS,
    WEIGHTS,
)


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
        self._kb_cache: list | None = None

    def _tokeniser(self, texte: str) -> set:
        import re
        mots = re.findall(r"[a-z0-9]+", texte.lower())
        return {m for m in mots if m not in self._STOPWORDS and len(m) > 2}

    def _charger_kb(self) -> list:
        if self._kb_cache is None:
            kb_path = Path(__file__).resolve().parents[2] / "data" / "kb" / "knowledge_base.json"
            try:
                with open(kb_path, encoding="utf-8") as f:
                    self._kb_cache = json.load(f).get("knowledge_base", [])
            except (FileNotFoundError, json.JSONDecodeError):
                self._kb_cache = []
        return self._kb_cache

    def _trouver_fiche_kb(self, ticket: str) -> dict | None:
        ticket_lower = ticket.lower()
        best_score, best_entry = 0, None
        for entry in self._charger_kb():
            score = sum(2 for mot in entry.get("mots_cles", []) if mot.lower() in ticket_lower)
            if any(mot in entry.get("probleme", "").lower() for mot in ticket_lower.split()):
                score += 1
            if score > best_score:
                best_score, best_entry = score, entry
        return best_entry if best_score > 0 else None

    def _extraire_termes_reference(self, fiche_kb: dict) -> set:
        sol = fiche_kb.get("solution", {})
        parts = [
            *fiche_kb.get("mots_cles", []),
            fiche_kb.get("probleme", ""),
            *sol.get("diagnostic", []),
            *sol.get("resolution", []),
        ]
        return self._tokeniser(" ".join(parts))

    def score_pertinence(self, reponse: str, ticket: str) -> dict[str, float]:
        """F1 textuel entre la réponse et la fiche KB du ticket."""
        if reponse == "ERREUR" or not reponse.strip():
            return {"score": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0}
        fiche = self._trouver_fiche_kb(ticket)
        if fiche is None:
            return {"score": 5.0, "precision": 0.0, "recall": 0.0, "f1": 0.0}
        termes_kb = self._extraire_termes_reference(fiche)
        termes_rep = self._tokeniser(reponse)
        if not termes_kb or not termes_rep:
            return {"score": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0}
        communs = termes_kb & termes_rep
        precision = len(communs) / len(termes_rep)
        recall = len(communs) / len(termes_kb)
        if precision + recall == 0:
            return {"score": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0}
        f1 = 2 * precision * recall / (precision + recall)
        return {
            "score": round(f1 * 10.0, 2),
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
        }

    def score_erreur(self, reponse: str) -> float:
        return 0.0 if reponse == "ERREUR" else 10.0

    def score_feedback(self, feedback: str) -> float:
        return float(self.feedback_scores.get(feedback, 0))

    def score_vitesse(self, temps_secondes: float) -> float:
        t = temps_secondes
        if t <= TIME_THRESHOLDS["excellent"]:
            return 10.0
        if t <= TIME_THRESHOLDS["good"]:
            return 10.0 - (t - TIME_THRESHOLDS["excellent"]) / (TIME_THRESHOLDS["good"] - TIME_THRESHOLDS["excellent"]) * 3.0
        if t <= TIME_THRESHOLDS["acceptable"]:
            return 7.0 - (t - TIME_THRESHOLDS["good"]) / (TIME_THRESHOLDS["acceptable"] - TIME_THRESHOLDS["good"]) * 6.0
        if t <= TIME_THRESHOLDS["slow"]:
            return max(0.0, 1.0 - (t - TIME_THRESHOLDS["acceptable"]) / (TIME_THRESHOLDS["slow"] - TIME_THRESHOLDS["acceptable"]))
        return 0.0

    def score_efficacite_tokens(self, nombre_tokens: int) -> float:
        n = nombre_tokens
        if n <= TOKEN_THRESHOLDS["excellent"]:
            return 10.0
        if n <= TOKEN_THRESHOLDS["good"]:
            return 10.0 - (n - TOKEN_THRESHOLDS["excellent"]) / (TOKEN_THRESHOLDS["good"] - TOKEN_THRESHOLDS["excellent"]) * 3.0
        if n <= TOKEN_THRESHOLDS["acceptable"]:
            return 7.0 - (n - TOKEN_THRESHOLDS["good"]) / (TOKEN_THRESHOLDS["acceptable"] - TOKEN_THRESHOLDS["good"]) * 6.0
        if n <= TOKEN_THRESHOLDS["excessive"]:
            return max(0.0, 1.0 - (n - TOKEN_THRESHOLDS["acceptable"]) / (TOKEN_THRESHOLDS["excessive"] - TOKEN_THRESHOLDS["acceptable"]))
        return 0.0

    def calculate_final_score(
        self,
        reponse: str,
        feedback: str,
        temps_secondes: float,
        nombre_tokens: int,
        ticket: str = "",
    ) -> dict[str, float]:
        se = self.score_erreur(reponse)
        sf = self.score_feedback(feedback)
        sv = self.score_vitesse(temps_secondes)
        st = self.score_efficacite_tokens(nombre_tokens)
        sp_result = self.score_pertinence(reponse, ticket) if ticket else {"score": 5.0, "precision": 0.0, "recall": 0.0, "f1": 0.0}
        sp = sp_result["score"]

        w = self.weights
        if reponse == "ERREUR":
            final = (se * w["erreur_penalty"] + sf * w["feedback"] * 0.2 + sv * w["vitesse"] * 0.2 + st * w["efficacite_tokens"] * 0.2 + sp * w["pertinence"] * 0.2) / (w["erreur_penalty"] + 0.2 * (1 - w["erreur_penalty"]))
        else:
            final = se * w["erreur_penalty"] + sf * w["feedback"] + sv * w["vitesse"] + st * w["efficacite_tokens"] + sp * w["pertinence"]

        return {
            "score_erreur": round(se, 2),
            "score_feedback": round(sf, 2),
            "score_vitesse": round(sv, 2),
            "score_efficacite_tokens": round(st, 2),
            "score_pertinence": round(sp, 2),
            "f1_details": {"precision": sp_result["precision"], "recall": sp_result["recall"], "f1": sp_result["f1"]},
            "score_final": round(max(SCORE_MIN, min(SCORE_MAX, final)), 2),
        }


_WEIGHTS_V2 = {
    "erreur_penalty":    0.20,
    "feedback":          0.28,
    "vitesse":           0.16,
    "efficacite_tokens": 0.16,
    "fact_checking":     0.20,
}


class EvaluationEngineV2(EvaluationEngine):
    """
    Scoring engine with a 5th dimension: A2A fact-checking accuracy.

    Compared to EvaluationEngine (v1), KB-relevance (pertinence) is replaced
    by an external fact-checking score sourced from A2AFactChecker.  Weights
    are adjusted accordingly; all other scoring methods are inherited unchanged.

    Usage:
        from src.bibops.adapters.a2a_client import A2AFactChecker
        checker = A2AFactChecker()
        engine  = EvaluationEngineV2()

        fc_result = checker.check_answer(response_text)
        scores    = engine.calculate_final_score(
            response_text, feedback, elapsed_s, tokens,
            accuracy_score=fc_result["accuracy_score"],
        )
    """

    def __init__(self):
        super().__init__()
        self.weights = _WEIGHTS_V2

    def score_fact_checking(self, accuracy_score: float | None) -> float:
        """Convert a 0–1 accuracy score to 0–10. None → neutral 5.0."""
        if accuracy_score is None:
            return 5.0
        return round(max(0.0, min(10.0, float(accuracy_score) * 10.0)), 2)

    def calculate_final_score(
        self,
        reponse: str,
        feedback: str,
        temps_secondes: float,
        nombre_tokens: int,
        accuracy_score: float | None = None,
        ticket: str = "",
    ) -> dict[str, float]:
        se = self.score_erreur(reponse)
        sf = self.score_feedback(feedback)
        sv = self.score_vitesse(temps_secondes)
        st = self.score_efficacite_tokens(nombre_tokens)
        sfc = self.score_fact_checking(accuracy_score)

        w = self.weights
        if reponse == "ERREUR":
            factor = 0.2
            final = (
                se * w["erreur_penalty"]
                + sf * w["feedback"] * factor
                + sv * w["vitesse"] * factor
                + st * w["efficacite_tokens"] * factor
                + sfc * w["fact_checking"] * factor
            ) / (w["erreur_penalty"] + factor * (1 - w["erreur_penalty"]))
        else:
            final = (
                se * w["erreur_penalty"]
                + sf * w["feedback"]
                + sv * w["vitesse"]
                + st * w["efficacite_tokens"]
                + sfc * w["fact_checking"]
            )

        return {
            "score_erreur": round(se, 2),
            "score_feedback": round(sf, 2),
            "score_vitesse": round(sv, 2),
            "score_efficacite_tokens": round(st, 2),
            "score_fact_checking": round(sfc, 2),
            "score_final": round(max(SCORE_MIN, min(SCORE_MAX, final)), 2),
        }


class EvaluationProcessor:
    """Lit un fichier de tickets JSON et génère les scores par règles."""

    def __init__(self, input_json_path: str, output_json_path: str):
        self.input_path = Path(input_json_path)
        self.output_path = Path(output_json_path)
        self.engine = EvaluationEngine()

    def evaluate_tickets(self) -> dict[str, Any]:
        with open(self.input_path, encoding="utf-8") as f:
            tickets = json.load(f)

        results: dict[str, Any] = {
            "date_evaluation": datetime.now().isoformat(),
            "total_tickets": len(tickets),
            "tickets_evalues": [],
            "statistiques_par_modele": {},
        }

        for ticket in tickets:
            modele = ticket.get("modele", "unknown")
            reponse = ticket.get("reponse", "ERREUR")
            feedback = ticket.get("feedback_utilisateur", "Inutile")
            temps = ticket.get("temps_reponse (s)", 0.0)
            tokens = ticket.get("nombre_tokens", 0)
            ticket_texte = ticket.get("ticket") or ticket.get("texte_ticket") or ticket.get("texte_utilisateur") or ""

            scores = self.engine.calculate_final_score(reponse, feedback, temps, tokens, ticket=ticket_texte)

            results["tickets_evalues"].append({
                "id_ticket": ticket.get("id_ticket", "unknown"),
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
            })

            stats = results["statistiques_par_modele"].setdefault(modele, {"count": 0, "scores": []})
            stats["count"] += 1
            stats["scores"].append(scores["score_final"])

        for stats in results["statistiques_par_modele"].values():
            s = stats.pop("scores")
            stats["score_moyen"] = round(statistics.mean(s), 2)
            stats["score_median"] = round(statistics.median(s), 2)
            stats["score_min"] = round(min(s), 2)
            stats["score_max"] = round(max(s), 2)
            stats["score_std_dev"] = round(statistics.stdev(s), 2) if len(s) > 1 else 0.0

        return results

    def save_results(self, results: dict[str, Any]) -> None:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"Résultats sauvegardés dans: {self.output_path}")

    def process(self) -> dict[str, Any]:
        print(f"Évaluation des tickets depuis: {self.input_path}")
        results = self.evaluate_tickets()
        self.save_results(results)
        return results


def filter_by_model(results: dict[str, Any], model_name: str) -> list[dict]:
    return [t for t in results["tickets_evalues"] if t["modele"] == model_name]


def compare_models(results: dict[str, Any]) -> dict[str, Any]:
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


if __name__ == "__main__":
    DATA_ROOT = Path(__file__).resolve().parents[2] / "data"
    INPUT_FILE = DATA_ROOT / "fixtures" / "benchmark" / "tickets_evalues_fake.json"
    OUTPUT_FILE = DATA_ROOT / "outputs" / "benchmark" / "tickets_evalues_scores.json"
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
