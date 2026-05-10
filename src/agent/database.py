import os
import sqlite3

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
DB_PATH = os.path.join(BASE_DIR, 'data', 'databases', 'bibops.db')


def initialiser_base_de_donnees():
    print("Création de la base de données BibOps (SQLite)...")
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS serveurs_it (
                nom TEXT PRIMARY KEY,
                statut TEXT,
                derniere_mise_a_jour TEXT
            )
        """)
        conn.commit()

    print(f"Base de données prête : {DB_PATH}")


if __name__ == "__main__":
    initialiser_base_de_donnees()
