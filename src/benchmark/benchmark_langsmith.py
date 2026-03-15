import os
import sqlite3
import time
from langsmith import traceable


os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_API_KEY"] = "***LANGSMITH_KEY_REMOVED***"
os.environ["LANGCHAIN_PROJECT"] = "BibOps-Local-Eval" # Nom de ton projet sur le dashboard

from src.agents.maestro import lancer_agent
from src.agents.outils import verifier_statut_serveur, chercher_documentation_technique, chercher_dans_kb
from src.llm_professor.evaluation_manager import LLMProfessor

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
DB_PATH = os.path.join(BASE_DIR, 'data', 'databases', 'bibops.db')

# 🎯 Décorateur LangSmith : Permet de capturer les entrées/sorties de l'agent
@traceable(name="Agent_Phi3_ReAct")
def executer_agent_trace(contexte, texte_utilisateur, outils, modele):
    """Encapsule l'appel à l'agent pour le tracer proprement dans LangSmith."""
    return lancer_agent(contexte, texte_utilisateur, outils_disponibles=outils, modele=modele)

def executer_benchmark():
    print("===  Lancement du Benchmark : Agent (Phi3) vs Juge (Mistral) ===")
    print(" Tracing LangSmith : ACTIVÉ")

    # Initialisation du Juge (Mistral)
    professeur = LLMProfessor(db_path=DB_PATH, modele_juge="mistral:latest")
    mes_outils = [verifier_statut_serveur, chercher_documentation_technique, chercher_dans_kb]
    modele_agent = "phi3:latest"

    # Récupération des tickets
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, contexte, texte_utilisateur FROM tickets")
        tickets = cursor.fetchall()

    if not tickets:
        print("Aucun ticket trouvé. Exécute src/agents/baseSQL.py d'abord.")
        return

    for ticket in tickets:
        ticket_id, contexte, texte_utilisateur = ticket
        print("\n" + "="*50)
        print(f" TICKET #{ticket_id} : {texte_utilisateur}")

        # 1. Exécution de l'Agent (Tracée par LangSmith)
        debut = time.time()
        reponse_agent = executer_agent_trace(contexte, texte_utilisateur, mes_outils, modele_agent)
        temps_execution = round(time.time() - debut, 2)
        print(f"\n[ Temps de réponse de l'Agent] : {temps_execution} s")

        # 2. Évaluation par le Juge (Tracée automatiquement via LangChain)
        professeur.evaluer_reponse(
            ticket_id=ticket_id,
            ticket_texte=texte_utilisateur,
            reponse_agent=reponse_agent,
            modele_agent=modele_agent,
            temps_reponse=temps_execution
        )

    print("\n  Va voir tes résultats sur https://smith.langchain.com")

if __name__ == "__main__":
    executer_benchmark()