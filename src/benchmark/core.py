import csv
import json
import time
import os
import sys
from datetime import datetime
import ollama

# CHATGPT
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
INPUT_CSV = os.path.join(BASE_DIR, 'data', 'inputs', 'benchmark', 'tickets_scenario_1.csv')
OUTPUT_JSON = os.path.join(BASE_DIR, 'data', 'outputs', 'benchmark', 'tickets_evalues.json')
# CHATGPT

FEEDBACK_OPTIONS = {
    "1": "Utile",
    "2": "Partiellement utile",
    "3": "Inutile",
}

# Options de generation pour garder le benchmark rapide et stable.
OLLAMA_OPTIONS = {
    "num_predict": 1024,
    "temperature": 0,
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


def _lire_champ(objet, cle):
    """Lit un champ depuis un dict ou un objet (attribut)."""
    if isinstance(objet, dict):
        return objet.get(cle)
    return getattr(objet, cle, None)


def extraire_texte_reponse(reponse_ollama):
    """Extrait le texte de reponse sans supposer un format unique."""
    message = _lire_champ(reponse_ollama, "message")
    contenu = _lire_champ(message, "content") if message is not None else None
    if isinstance(contenu, str):
        return contenu
    return ""


def extraire_compteurs_tokens(reponse_ollama):
    """Compte les tokens via metadonnees natives Ollama, sans approximation."""
    # Format Ollama chat classique
    prompt_eval_count = _lire_champ(reponse_ollama, "prompt_eval_count")
    eval_count = _lire_champ(reponse_ollama, "eval_count")
    if isinstance(prompt_eval_count, int) and isinstance(eval_count, int):
        return prompt_eval_count + eval_count, "ollama_native"

    # Format type usage (compatibilite clients/API differents)
    usage = _lire_champ(reponse_ollama, "usage")
    if isinstance(usage, dict):
        total_tokens = usage.get("total_tokens")
        if isinstance(total_tokens, int):
            return total_tokens, "usage_total_tokens"

        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")
        if isinstance(prompt_tokens, int) and isinstance(completion_tokens, int):
            return prompt_tokens + completion_tokens, "usage_prompt_plus_completion"

    # Cas ou l'API ne fournit pas de compteur fiable pour cette requete.
    return None, "native_tokens_absents"

def run_benchmark(model_names=None):
    if model_names is None:
        model_names = ["phi3:latest"]
    elif isinstance(model_names, str):
        model_names = [model_names]

    print(f"Benchmark BibOps sur les modèles : {', '.join(model_names)}\n")

    resultats = []

    # Lecture des tickets
    with open(INPUT_CSV, mode='r', encoding='utf-8') as file:
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

if __name__ == "__main__":
    # Usage:
    # python src/bibops/benchmark/benchmark.py
    # python src/bibops/benchmark/benchmark.py phi3:latest mistral:latest
    # python src/bibops/benchmark/benchmark.py "phi3:latest,mistral:latest"
    modeles_cli = []
    for arg in sys.argv[1:]:
        modeles_cli.extend([m.strip() for m in arg.split(",") if m.strip()])

    if not modeles_cli:
        modeles_cli = ["phi3:latest"]

    run_benchmark(model_names=modeles_cli)

# Le "Cold Start" (Démarrage à froid). Lors de la première question, Ollama doit charger le modèle d'un giga-octet
# depuis le disque dur vers la mémoire vive (RAM/VRAM)
# Pour les questions suivantes, le modèle est déjà "chaud" en mémoire, donc il répond beaucoup plus vite !
