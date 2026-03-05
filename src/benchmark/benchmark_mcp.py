import sqlite3
import time
import os
import ollama

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
DB_PATH = os.path.join(BASE_DIR, 'data', 'bibops.db')

def run_benchmark_sql(model_name="llama3.2:1b"):
    print(f" Benchmark BibOps connecté à SQLite sur le modèle : {model_name}\n")

    if not os.path.exists(DB_PATH):
        print(" Erreur : La base de données n'existe pas. Lancez db_setup.py d'abord !")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Lecture des tickets depuis SQL
    cursor.execute("SELECT id, contexte, texte_utilisateur FROM tickets")
    tickets = cursor.fetchall()

    for ticket in tickets:
        ticket_id, contexte_systeme, ticket_texte = ticket

        print(f"⏳ Traitement du ticket #{ticket_id}...")

        messages_ia = [
            {'role': 'system', 'content': contexte_systeme},
            {'role': 'user', 'content': ticket_texte}
        ]

        try:
            start_time = time.time()
            reponse = ollama.chat(model=model_name, messages=messages_ia)
            latency = time.time() - start_time
            texte_ia = reponse['message']['content']
            print(f"    Fait en {latency:.2f} s.")

        except Exception as e:
            print(f"    Erreur : {e}")
            texte_ia = "ERREUR"
            latency = 0.0

        # Sauvegarde du résultat dans SQL (note_juge = 0 par défaut)
        cursor.execute('''
                       INSERT INTO evaluations (ticket_id, modele, reponse_ia, temps_reponse_s, note_juge)
                       VALUES (?, ?, ?, ?, ?)
                       ''', (ticket_id, model_name, texte_ia, round(latency, 2), 0))

        conn.commit()

    conn.close()
    print("\nÉvaluations terminées et sauvegardées dans la table 'evaluations' de SQLite !")

if __name__ == "__main__":
    run_benchmark_sql()