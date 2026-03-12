"""
Module d'évaluation des réponses des modèles LLM basé sur plusieurs critères.

Ce module score chaque réponse sur 10 en fonction de :
- Absence d'erreur (ERREUR vs réponse valide)
- Feedback utilisateur (Utile/Partiellement utile/Inutile)
- Temps de réponse (rapidité)
- Efficacité en tokens (consommation de ressources)

Les scores sont sauvegardés dans un fichier séparé avec structure permettant (éventuellement)
le filtrage et la comparaison entre modèles.
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import statistics
import sys

# Gestion compatibilité des imports
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


class EvaluationEngine:
    """Moteur d'évaluation des réponses LLM"""

    def __init__(self):
        """Initialise le moteur d'évaluation"""
        self.weights = WEIGHTS
        self.feedback_scores = FEEDBACK_SCORES

    def score_erreur(self, reponse: str) -> float:
        """
        Score basé sur la présence ou absence d'erreur.
        - Si réponse = "ERREUR" : score 0
        - Sinon : score 10
        """
        if reponse == "ERREUR":
            return 0.0
        return 10.0

    def score_feedback(self, feedback: str) -> float:
        """
        Score basé sur le feedback utilisateur comme critère de pertinence.
        Retourne la valeur mappée ou 0 si feedback inconnu.
        """
        return float(self.feedback_scores.get(feedback, 0))

    def score_vitesse(self, temps_secondes: float) -> float:
        """
        Score basé sur le temps de réponse.
        """
        if temps_secondes <= TIME_THRESHOLDS["excellent"]:
            return 10.0
        elif temps_secondes <= TIME_THRESHOLDS["good"]:
            # Interpolation linéaire entre 10 et 7
            return 10.0 - (temps_secondes - TIME_THRESHOLDS["excellent"]) / (
                TIME_THRESHOLDS["good"] - TIME_THRESHOLDS["excellent"]
            ) * 3.0
        elif temps_secondes <= TIME_THRESHOLDS["acceptable"]:
            # Interpolation linéaire entre 7 et 1
            return 7.0 - (temps_secondes - TIME_THRESHOLDS["good"]) / (
                TIME_THRESHOLDS["acceptable"] - TIME_THRESHOLDS["good"]
            ) * 6.0
        elif temps_secondes <= TIME_THRESHOLDS["slow"]:
            # Interpolation linéaire entre 1 et 0
            return max(
                0.0,
                1.0
                - (temps_secondes - TIME_THRESHOLDS["acceptable"])
                / (TIME_THRESHOLDS["slow"] - TIME_THRESHOLDS["acceptable"]),
            )
        else:
            return 0.0

    def score_efficacite_tokens(self, nombre_tokens: int) -> float:
        """
        Score basé sur l'efficacité en terme de tokens.
        """
        if nombre_tokens <= TOKEN_THRESHOLDS["excellent"]:
            return 10.0
        elif nombre_tokens <= TOKEN_THRESHOLDS["good"]:
            # Interpolation linéaire entre 10 et 7
            return 10.0 - (nombre_tokens - TOKEN_THRESHOLDS["excellent"]) / (
                TOKEN_THRESHOLDS["good"] - TOKEN_THRESHOLDS["excellent"]
            ) * 3.0
        elif nombre_tokens <= TOKEN_THRESHOLDS["acceptable"]:
            # Interpolation linéaire entre 7 et 1
            return 7.0 - (nombre_tokens - TOKEN_THRESHOLDS["good"]) / (
                TOKEN_THRESHOLDS["acceptable"] - TOKEN_THRESHOLDS["good"]
            ) * 6.0
        elif nombre_tokens <= TOKEN_THRESHOLDS["excessive"]:
            # Interpolation linéaire entre 1 et 0
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
    ) -> Dict[str, float]:
        """
        Calcule le score final pondéré.

        Args:
            reponse: Le contenu de la réponse ou "ERREUR"
            feedback: Feedback utilisateur (Utile/Partiellement utile/Inutile)
            temps_secondes: Temps de réponse en secondes
            nombre_tokens: Nombre de tokens utilisés

        Returns:
            Dict contenant les scores individuels + le score final
        """
        # Calcul des scores individuels
        score_erreur = self.score_erreur(reponse)
        score_feedback = self.score_feedback(feedback)
        score_vitesse = self.score_vitesse(temps_secondes)
        score_efficacite = self.score_efficacite_tokens(nombre_tokens)

        # Application de la pénalité si erreur dans la réponse
        if reponse == "ERREUR":
            # La réponse est ERREUR : score final maximal = 0 + contribution des autres critères pénalisés
            final_score = (
                score_erreur * self.weights["erreur_penalty"]
                + score_feedback * self.weights["feedback"] * 0.2  # Réduit à 20% de poids
                + score_vitesse * self.weights["vitesse"] * 0.2 #idem
                + score_efficacite * self.weights["efficacite_tokens"] * 0.2
            ) / (
                # normalisation du résultat en / par la somme des poids
                self.weights["erreur_penalty"] + 0.2 * (1 - self.weights["erreur_penalty"])
            )
        else:
            # Calcul pondéré normal
            final_score = (
                score_erreur * self.weights["erreur_penalty"]
                + score_feedback * self.weights["feedback"]
                + score_vitesse * self.weights["vitesse"]
                + score_efficacite * self.weights["efficacite_tokens"]
            )

        # Clamping au range [SCORE_MIN, SCORE_MAX] (mesure de sécurité)
        final_score = max(SCORE_MIN, min(SCORE_MAX, final_score))

        return {
            "score_erreur": round(score_erreur, 2),
            "score_feedback": round(score_feedback, 2),
            "score_vitesse": round(score_vitesse, 2),
            "score_efficacite_tokens": round(score_efficacite, 2),
            "score_final": round(final_score, 2),
        }


class EvaluationProcessor:
    """Prend un fichier de tickets et génère les scores"""

    def __init__(self, input_json_path: str, output_json_path: str):
        """
        Args:
            input_json_path: Chemin vers le fichier tickets_evalues_fake.json
            output_json_path: Chemin vers le fichier de résultats avec scores
        """
        self.input_path = Path(input_json_path)
        self.output_path = Path(output_json_path)
        self.engine = EvaluationEngine()

    def evaluate_tickets(self) -> Dict[str, Any]:
        """
        Lit le fichier de tickets et évalue chacun.

        Returns:
            Dict contenant les résultats d'évaluation
        """
        # Lecture du fichier d'entrée
        with open(self.input_path, "r", encoding="utf-8") as f:
            tickets = json.load(f)

        # Évaluation de chaque ticket
        results = {
            "date_evaluation": datetime.now().isoformat(),
            "total_tickets": len(tickets),
            "tickets_evalues": [],
            "statistiques_par_modele": {},
        }

        for ticket in tickets:
            # Extraction des données
            id_ticket = ticket.get("id_ticket", "unknown")
            modele = ticket.get("modele", "unknown")
            reponse = ticket.get("reponse", "ERREUR")
            feedback = ticket.get("feedback_utilisateur", "Inutile")
            temps = ticket.get("temps_reponse (s)", 0.0)
            tokens = ticket.get("nombre_tokens", 0)

            # Calcul du score
            scores = self.engine.calculate_final_score(reponse, feedback, temps, tokens)

            # Création du résultat pour ce ticket
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
                },
                # Garder les données brutes pour traçabilité
                "donnees_brutes": {
                    "feedback_utilisateur": feedback,
                    "temps_reponse_s": temps,
                    "nombre_tokens": tokens,
                    "reponse_erreur": reponse == "ERREUR",
                },
            }

            results["tickets_evalues"].append(result_ticket)

            # Accumulation des stats par modèle
            if modele not in results["statistiques_par_modele"]:
                results["statistiques_par_modele"][modele] = {
                    "count": 0,
                    "scores": [],
                }
            results["statistiques_par_modele"][modele]["count"] += 1
            results["statistiques_par_modele"][modele]["scores"].append(
                scores["score_final"]
            )

        # Calcul des statistiques par modèle
        for modele, stats in results["statistiques_par_modele"].items():
            scores = stats["scores"]
            stats["score_moyen"] = round(statistics.mean(scores), 2)
            stats["score_median"] = round(statistics.median(scores), 2)
            stats["score_min"] = round(min(scores), 2)
            stats["score_max"] = round(max(scores), 2)
            if len(scores) > 1:
                stats["score_std_dev"] = round(statistics.stdev(scores), 2)
            else:
                stats["score_std_dev"] = 0.0
            # Supprimer la liste brute de scores
            del stats["scores"]

        return results

    def save_results(self, results: Dict[str, Any]) -> None:
        """
        Sauvegarde les résultats dans le fichier de sortie.

        Args:
            results: Dict contenant les résultats d'évaluation
        """
        # Créer le répertoire s'il n'existe pas
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        # Sauvegarder en JSON avec indentation
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"✓ Résultats sauvegardés dans: {self.output_path}")

    def process(self) -> Dict[str, Any]:
        """
        Processe complètement le fichier d'entrée.
        """
        print(f"Évaluation des tickets depuis: {self.input_path}")
        results = self.evaluate_tickets()
        self.save_results(results)
        return results


def filter_by_model(results: Dict[str, Any], model_name: str) -> List[Dict]:
    """
    Filtre les résultats par nom de modèle.

    Args:
        results: Dict retourné par EvaluationProcessor.evaluate_tickets()
        model_name: Nom du modèle à filtrer (ex: "llama3.2:1b")

    Returns:
        Liste des tickets évalués pour ce modèle
    """
    return [
        ticket for ticket in results["tickets_evalues"]
        if ticket["modele"] == model_name
    ]


def compare_models(results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Crée un résumé comparatif des modèles.

    Args:
        results: Dict retourné par EvaluationProcessor.evaluate_tickets()

    Returns:
        Dict avec statistiques comparatives entre modèles
    """
    comparison = {}
    for modele, stats in results["statistiques_par_modele"].items():
        comparison[modele] = {
            "nombre_tickets": stats["count"],
            "score_moyen": stats["score_moyen"],
            "score_median": stats["score_median"],
            "score_range": f"{stats['score_min']}-{stats['score_max']}",
            "score_std_dev": stats["score_std_dev"],
        }
    
    # Tri par score moyen (meilleur d'abord)
    comparison = dict(
        sorted(comparison.items(), key=lambda x: x[1]["score_moyen"], reverse=True)
    )
    
    return comparison


if __name__ == "__main__":
    # Chemins des fichiers
    DATA_DIR = Path(__file__).parent.parent.parent / "data" / "benchmark"
    INPUT_FILE = DATA_DIR / "tickets_evalues_fake.json"
    OUTPUT_FILE = DATA_DIR / "tickets_evalues_scores.json"

    # Création et lancement du processeur
    processor = EvaluationProcessor(str(INPUT_FILE), str(OUTPUT_FILE))
    results = processor.process()

    # Affichage des statistiques
    print("\n" + "=" * 70)
    print("STATISTIQUES PAR MODÈLE")
    print("=" * 70)
    comparison = compare_models(results)
    for modele, stats in comparison.items():
        print(f"\n📦 {modele}")
        print(f"   Tickets: {stats['nombre_tickets']}")
        print(f"   Score moyen: {stats['score_moyen']}/10")
        print(f"   Score médian: {stats['score_median']}/10")
        print(f"   Score min-max: {stats['score_range']}")
        print(f"   Écart-type: {stats['score_std_dev']}")
