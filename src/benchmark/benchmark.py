import csv
import json
import time
import os
from datetime import datetime
import ollama

# CHATGPT
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
INPUT_CSV = os.path.join(BASE_DIR, 'data', 'benchmark', 'tickets_scenario_1.csv')
OUTPUT_JSON = os.path.join(BASE_DIR, 'data', 'benchmark', 'tickets_evalues.json')
# CHATGPT

FEEDBACK_OPTIONS = {
    "1": "Utile",
    "2": "Partiellement utile",
    "3": "Inutile",
}


def demander_feedback_utilisateur():
    """Demande un feedback utilisateur standardise pour chaque reponse."""
    while True:
        print("\nAvez-vous trouve cette reponse utile ?")
        print("  1. Utile")
        print("  2. Partiellement utile")
        print("  3. Inutile")
        choix = input("Votre choix (1/2/3) : ").strip()

        if choix in FEEDBACK_OPTIONS:
            return FEEDBACK_OPTIONS[choix]

        print("Choix invalide. Merci de saisir 1, 2 ou 3.")


def extraire_compteurs_tokens(_reponse_ollama, texte_reponse):
    """Approximation simple des tokens (1 token ~= 4 caracteres)."""
    return len(texte_reponse) // 4

def run_benchmark(model_name="phi3:latest"):
    print(f"Benchmark BibOps sur le modèle : {model_name}\n")

    resultats = []

    # Lecture des tickets
    with open(INPUT_CSV, mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)

        for row in reader:
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
                reponse = ollama.chat(
                    model=model_name,
                    messages=prompt
                )

                # STOP
                latency = time.time() - start_time
                texte_ia = reponse['message']['content']
                nombre_tokens = extraire_compteurs_tokens(reponse, texte_ia)

                print(f"Fait en {latency:.2f} secondes. Tokens total: {nombre_tokens}.")

            except Exception as e:
                print(f"Erreur sur le ticket {ticket_id}: {e}")
                texte_ia = "ERREUR"
                latency = 0.0
                dateheure_capture = datetime.now().isoformat()
                nombre_tokens = 0

            print("\nRéponse du modèle :")
            print(texte_ia)
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
    # On doit mettre d autres models que celui la pour comparer ( ou les mixer peut etre ... )
    run_benchmark(model_name="phi3:latest")

# Le "Cold Start" (Démarrage à froid). Lors de la première question, Ollama doit charger le modèle d'un giga-octet
# depuis le disque dur vers la mémoire vive (RAM/VRAM)
# Pour les questions suivantes, le modèle est déjà "chaud" en mémoire, donc il répond beaucoup plus vite !
