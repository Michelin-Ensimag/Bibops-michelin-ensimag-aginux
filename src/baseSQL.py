import sqlite3
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
DB_PATH = os.path.join(BASE_DIR, 'data', 'bibops.db')

def initialiser_base_de_donnees():
    print("Création de la base de données BibOps (SQLite)...")

    # On s'assure que le dossier data/ existe
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Table des serveurs IT
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS serveurs_it (
                                                              nom TEXT PRIMARY KEY,
                                                              statut TEXT,
                                                              derniere_mise_a_jour TEXT
                   )
                   ''')

    # 2. Table des tickets (Le carburant)
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS tickets (
                                                          id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                          contexte TEXT,
                                                          texte_utilisateur TEXT
                   )
                   ''')

    # 3. Table des évaluations (Le résultat final)
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS evaluations (
                                                              id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                              ticket_id INTEGER,
                                                              modele TEXT,
                                                              reponse_ia TEXT,
                                                              temps_reponse_s REAL,
                                                              note_juge INTEGER,
                                                              FOREIGN KEY(ticket_id) REFERENCES tickets(id)
                       )
                   ''')

    # --- Nettoyage avant insertion ---
    cursor.execute('DELETE FROM serveurs_it')
    cursor.execute('DELETE FROM tickets')

    # --- Insertion de fausses données de départ ---
    serveurs = [
        ('VPN', 'HORS LIGNE (Incident 4042)', '2026-02-26'),
        ('CISCO', 'EN LIGNE', '2026-02-26'),
        ('OUTLOOK', 'EN LIGNE', '2026-02-26')
    ]
    cursor.executemany('INSERT INTO serveurs_it VALUES (?, ?, ?)', serveurs)

    tickets = [
        ("Tu es un technicien support IT chez Michelin.", "Mon VPN Cisco ne marche plus."),
        ("Tu es un expert RH chez Michelin.", "Combien de jours de congés me reste-t-il ?"),
        ("Tu es un technicien support IT.", "Mon imprimante affiche erreur 404.")
    ]
    cursor.executemany('INSERT INTO tickets (contexte, texte_utilisateur) VALUES (?, ?)', tickets)

    conn.commit()
    conn.close()
    print(f"Base de données prête : {DB_PATH}")

if __name__ == "__main__":
    initialiser_base_de_donnees()