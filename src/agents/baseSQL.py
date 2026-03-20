import sqlite3
import os

# On recule de deux dossiers : src/agents/ -> src/ -> racine/
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
DB_PATH = os.path.join(BASE_DIR, 'data', 'databases', 'bibops.db')

def initialiser_base_de_donnees():
    print("Création de la base de données BibOps (SQLite)...")
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''CREATE TABLE IF NOT EXISTS serveurs_it (nom TEXT PRIMARY KEY, statut TEXT, derniere_mise_a_jour TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, contexte TEXT, texte_utilisateur TEXT)''')
    # Ajout de la colonne justification_juge pour llm_professor plus tard
    cursor.execute('''CREATE TABLE IF NOT EXISTS evaluations (id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id INTEGER, modele TEXT, reponse_ia TEXT, temps_reponse_s REAL, note_juge INTEGER, justification_juge TEXT, FOREIGN KEY(ticket_id) REFERENCES tickets(id))''')

    # Migration : ajoute justification_juge si la table existait avant cette colonne
    try:
        cursor.execute("ALTER TABLE evaluations ADD COLUMN justification_juge TEXT")
    except sqlite3.OperationalError:
        pass  # colonne déjà présente

    # Upsert serveurs : on remplace uniquement les données de référence
    cursor.execute('DELETE FROM serveurs_it')
    serveurs = [
        ('VPN',        'HORS LIGNE (Incident 4042)', '2026-02-26'),
        ('CISCO',      'EN LIGNE',                   '2026-02-26'),
        ('OUTLOOK',    'EN LIGNE',                   '2026-02-26'),
        ('IMPRIMANTE', 'EN LIGNE',                   '2026-02-26'),
    ]
    cursor.executemany('INSERT INTO serveurs_it VALUES (?, ?, ?)', serveurs)

    # On insère les tickets de test seulement si la table est vide (pour ne pas perdre les évaluations liées)
    cursor.execute('SELECT COUNT(*) FROM tickets')
    if cursor.fetchone()[0] == 0:
        tickets = [
            ("Tu es un technicien support IT Michelin.", "Mon VPN Cisco ne marche plus."),
            ("Tu es un expert RH chez Michelin.", "Combien de jours de congés me reste-t-il ?")
        ]
        cursor.executemany('INSERT INTO tickets (contexte, texte_utilisateur) VALUES (?, ?)', tickets)

    conn.commit()
    conn.close()
    print(f"Base de données prête : {DB_PATH}")

if __name__ == "__main__":
    initialiser_base_de_donnees()
