import sqlite3
import time
import os
from typing import Optional

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))

from src.it_support.agent_maestro import lancer_agent
from src.it_support.outils import verifier_statut_serveur

DB_PATH = os.path.join(BASE_DIR, 'data', 'databases', 'bibops.db')


def _resolve_max_tickets(explicit_value: Optional[int] = None) -> Optional[int]:
    if explicit_value is not None and explicit_value > 0:
        return explicit_value

    raw = os.environ.get("BIBOPS_MAX_TICKETS", "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
        return value if value > 0 else None
    except ValueError:
        return None


def run_benchmark_agent(model_name="phi3:latest", max_tickets: Optional[int] = None):
    print(f"🚀 Démarrage du Benchmark de l'Agent BibOps sur le modèle : {model_name}\n")

    if not os.path.exists(DB_PATH):
        print("❌ Erreur : La base de données n'existe pas. Lancez setup_sql.py d'abord !")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Lecture des tickets depuis SQL (contexte + texte)
    cursor.execute("SELECT id, contexte, texte_utilisateur FROM tickets")
    tickets = cursor.fetchall()
    effective_max_tickets = _resolve_max_tickets(max_tickets)
    if effective_max_tickets is not None:
        tickets = tickets[:effective_max_tickets]
        print(f"🔧 Limitation active: {effective_max_tickets} ticket(s) max.")

    for ticket in tickets:
        ticket_id, contexte_ticket, ticket_texte = ticket
        print(f"\n" + "="*50)
        print(f"⏳ ÉVALUATION DU TICKET #{ticket_id}...")
        print("="*50)

        try:
            start_time = time.time()

            # 🌟 LA MAGIE EST ICI : On évalue toute la pipeline de l'Agent (RCA + Tools + LLM)
            texte_ia = lancer_agent(
                contexte=contexte_ticket,
                ticket_utilisateur=ticket_texte,
                outils_disponibles=[verifier_statut_serveur],
                modele=model_name
            )

            latency = time.time() - start_time
            print(f"\n✅ Ticket #{ticket_id} résolu en {latency:.2f} secondes.")

        except Exception as e:
            print(f"\n❌ Erreur pendant l'exécution de l'agent : {e}")
            texte_ia = "ERREUR"
            latency = 0.0

        # Sauvegarde du résultat dans SQL (note_juge = 0 par défaut)
        cursor.execute('''
                       INSERT INTO evaluations (ticket_id, modele, reponse_ia, temps_reponse_s, note_juge, justification_juge)
                       VALUES (?, ?, ?, ?, ?, ?)
                       ''', (ticket_id, model_name, texte_ia, round(latency, 2), 0, ""))

        conn.commit()

    conn.close()
    print("\n📁 Évaluations de l'Agent terminées et sauvegardées dans SQLite !")

if __name__ == "__main__":
    run_benchmark_agent(model_name="phi3:latest")
