import csv
import json
import time
import os
import ollama

# CHATGPT
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
INPUT_CSV = os.path.join(BASE_DIR, 'data', 'tickets_scenario_1.csv')
OUTPUT_JSON = os.path.join(BASE_DIR, 'data', 'tickets_evalues.json')
# CHATGPT

def run_benchmark(model_name="llama3.2:1b"):
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

                # Appel à Ollama
                reponse = ollama.chat(
                    model=model_name,
                    messages=prompt
                )

                # STOP
                latency = time.time() - start_time
                texte_ia = reponse['message']['content']

                print(f"Fait en {latency:.2f} secondes.")

            except Exception as e:
                print(f"Erreur sur le ticket {ticket_id}: {e}")
                texte_ia = "ERREUR"
                latency = 0.0


            # 3. Stockage des métriques
            resultats.append({
                "id_ticket": ticket_id,
                "contexte": contexte_systeme,
                "ticket": ticket_texte,
                "modele": model_name,
                "reponse": texte_ia,
                "temps_reponse (s)": round(latency, 2)
            })

    # On met les resultats dans un fichier json pour les analyser apres dans le fichier analyse_du_projet.ipynb

    with open(OUTPUT_JSON, mode='w', encoding='utf-8') as f_out:
        json.dump(resultats, f_out, indent=4, ensure_ascii=False)

    print(f"\nrésultats du Benchmark dans : {OUTPUT_JSON}")

if __name__ == "__main__":
    # On doit mettre d autres models que celui la pour comparer ( ou les mixer peut etre ... )
    run_benchmark(model_name="llama3.2:1b")

# Le "Cold Start" (Démarrage à froid). Lors de la première question, Ollama doit charger le modèle d'un giga-octet
# depuis le disque dur vers la mémoire vive (RAM/VRAM)
# Pour les questions suivantes, le modèle est déjà "chaud" en mémoire, donc il répond beaucoup plus vite !
