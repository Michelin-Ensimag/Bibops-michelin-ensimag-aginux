import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime

import ollama

from src.common.config import BASE_DIR as PROJECT_ROOT
from src.common.config import DEFAULT_AGENT_MODEL, OLLAMA_OPTIONS, OUTPUT_DIR
from src.common.config import INPUT_CSV as DEFAULT_INPUT_CSV
from src.common.text import extraire_compteurs_tokens, extraire_texte_reponse

BASE_DIR = str(PROJECT_ROOT)
INPUT_CSV = str(DEFAULT_INPUT_CSV)
OUTPUT_JSON = str(OUTPUT_DIR / "tickets_evalues.json")

FEEDBACK_OPTIONS = {
    "1": "Utile",
    "2": "Partiellement utile",
    "3": "Inutile",
}

def _is_non_interactive_mode() -> bool:
    return os.environ.get("BIBOPS_NON_INTERACTIVE", "0") == "1" or not sys.stdin.isatty()


def _default_feedback_choice() -> str:
    raw = os.environ.get("BIBOPS_DEFAULT_FEEDBACK", "2").strip()
    if raw in FEEDBACK_OPTIONS:
        return raw
    normalized = raw.lower()
    for key, label in FEEDBACK_OPTIONS.items():
        if normalized == label.lower():
            return key
    return "2"


def demander_feedback_utilisateur():
    """Demande un feedback utilisateur standardise pour chaque reponse."""
    if _is_non_interactive_mode():
        choice = _default_feedback_choice()
        default_feedback = FEEDBACK_OPTIONS[choice]
        print(f"[Mode non interactif] feedback automatique: {choice} ({default_feedback})")
        return default_feedback

    while True:
        print("\nAvez-vous trouve cette reponse utile ?")
        print("  1. Utile")
        print("  2. Partiellement utile")
        print("  3. Inutile")
        try:
            choix = input("Votre choix (1/2/3) : ").strip()
        except EOFError:
            choice = _default_feedback_choice()
            default_feedback = FEEDBACK_OPTIONS[choice]
            print(f"\n[EOF] feedback automatique: {choice} ({default_feedback})")
            return default_feedback

        if choix in FEEDBACK_OPTIONS:
            return FEEDBACK_OPTIONS[choix]

        print("Choix invalide. Merci de saisir 1, 2 ou 3.")


def run_benchmark(model_names=None):
    if model_names is None:
        model_names = [DEFAULT_AGENT_MODEL]
    elif isinstance(model_names, str):
        model_names = [model_names]

    print(f"Benchmark BibOps sur les modèles : {', '.join(model_names)}\n")

    resultats = []

    # Lecture des tickets
    with open(INPUT_CSV, encoding='utf-8') as file:
        tickets = list(csv.DictReader(file))
    max_tickets_env = os.environ.get("BIBOPS_MAX_TICKETS", "").strip()
    if max_tickets_env:
        try:
            max_tickets = int(max_tickets_env)
            if max_tickets > 0:
                tickets = tickets[:max_tickets]
        except ValueError:
            pass

    for model_name in model_names:
        print("=" * 70)
        print(f"Modèle en cours : {model_name}")
        print("=" * 70)

        for row in tickets:
            ticket_id = row.get('id', 'Inconnu')
            ticket_texte = row.get('ticket', '')
            # LECTURE DU CONTEXTE DEPUIS LE CSV (La magie opère ici)
            contexte_systeme = row.get('contexte', 'Tu es un assistant utile.')

            print(f"Traitement du ticket #{ticket_id}...")

            # Le prompt système (Je pense que c est une tache a part qu on doit prendre en compte)
            prompt = [
                {'role': 'system', 'content': contexte_systeme},
                {'role': 'user', 'content': ticket_texte}
            ]

            try:
                #START
                start_time = time.time()
                dateheure_capture = datetime.now().isoformat()

                # Appel à Ollama
                print("  -> Appel Ollama en cours...")
                reponse = ollama.chat(
                    model=model_name,
                    messages=prompt,
                    options=OLLAMA_OPTIONS,
                )

                # STOP
                latency = time.time() - start_time
                texte_ia = extraire_texte_reponse(reponse)
                if not texte_ia:
                    raise RuntimeError("Reponse Ollama vide ou format inattendu (message.content manquant).")
                nombre_tokens, _ = extraire_compteurs_tokens(reponse)

                print(
                    f"Fait en {latency:.2f} secondes. "
                    f"Traitement termine."
                )

                if nombre_tokens is None:
                    print("[Avertissement] Compteurs de tokens natifs absents pour ce ticket (aucune approximation appliquee).")

            except Exception as e:
                print(f"Erreur sur le ticket {ticket_id}: {e}")
                texte_ia = "ERREUR"
                latency = 0.0
                dateheure_capture = datetime.now().isoformat()
                nombre_tokens = None

            print("\nRéponse du modèle :")
            print(texte_ia)
            print("\nEn attente du feedback utilisateur...")
            feedback_utilisateur = demander_feedback_utilisateur()


            # 3. Stockage des métriques
            resultats.append({
                "id_ticket": ticket_id,
                "contexte": contexte_systeme,
                "ticket": ticket_texte,
                "modele": model_name,
                "reponse": texte_ia,
                "temps_reponse (s)": round(latency, 2),
                "nombre_tokens": nombre_tokens,
                "dateheure": dateheure_capture,
                "feedback_utilisateur": feedback_utilisateur
            })

    # On met les resultats dans un fichier json pour les analyser apres dans le fichier analyse_du_projet.ipynb

    with open(OUTPUT_JSON, mode='w', encoding='utf-8') as f_out:
        json.dump(resultats, f_out, indent=4, ensure_ascii=False)

    print(f"\nrésultats du Benchmark dans : {OUTPUT_JSON}")

def main() -> None:
    parser = argparse.ArgumentParser(description="Run the historical local Ollama benchmark.")
    parser.add_argument(
        "models",
        nargs="*",
        help="Ollama model names. Comma-separated values are accepted.",
    )
    args = parser.parse_args()

    modeles_cli = []
    for arg in args.models:
        modeles_cli.extend([m.strip() for m in arg.split(",") if m.strip()])

    if not modeles_cli:
        modeles_cli = [DEFAULT_AGENT_MODEL]

    run_benchmark(model_names=modeles_cli)


if __name__ == "__main__":
    main()

# Le "Cold Start" (Démarrage à froid). Lors de la première question, Ollama doit charger le modèle d'un giga-octet
# depuis le disque dur vers la mémoire vive (RAM/VRAM)
# Pour les questions suivantes, le modèle est déjà "chaud" en mémoire, donc il répond beaucoup plus vite !
