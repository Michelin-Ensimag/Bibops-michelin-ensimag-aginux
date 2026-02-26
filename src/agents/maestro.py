# CHATGPT



import sys
import os

# On s'assure que le projet est dans le path pour les imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import ollama
from src.agents.outils import verifier_statut_serveur
from src.agents.rca_engine import RCAEngine

# Initialisation du moteur RCA
rca = RCAEngine()

contexte_entreprise = "L'entreprise est Michelin. Le VPN principal est Cisco."
contexte_generale = f"""
Tu es l'agent IA de support informatique (BibOps). 
Contexte actuel : {contexte_entreprise}

Règles :
1. Si l'utilisateur a un problème avec un service, utilise TOUJOURS l'outil 'verifier_statut_serveur' avant de répondre.
2. Sois concis et professionnel.
"""

def lancer_agent(ticket_utilisateur, contexte_systeme, outils_disponibles, modele="llama3.2:1b"):
    print(f"\nUtilisateur : {ticket_utilisateur}")

    # A : L'agent réfléchit avec son outil
    # --- ON AJOUTE LE RCA ICI ---
    print(f"[RCA] Analyse technique du ticket...")
    diagnostic = rca.analyser_cause_racine(ticket_utilisateur)
    print(f"[RCA] Diagnostic : {diagnostic}")
    
    contexte_avec_rca = f"{contexte_generale}\n\nDiagnostic RCA : {diagnostic}"
    # ----------------------------

    messages = [
        {'role': 'system', 'content': contexte_avec_rca},
        {'role': 'user', 'content': ticket_utilisateur}
    ]

    reponse = ollama.chat(
        model=modele,
        messages=messages,
        tools=outils_disponibles
    )

    messages.append(reponse['message'])

    # B : L'agent a-t-il appelé l'outil ?
    if not reponse['message'].get('tool_calls'):
        contenu_direct = reponse['message']['content']
        print(f"Agent (Direct) : {contenu_direct}")
        return contenu_direct

    # C : Exécution de l'outil (Version originale conservée)
    for tool in reponse['message']['tool_calls']:
        nom_outil = tool['function']['name']

        if nom_outil == 'verifier_statut_serveur':
            # On récupère l'argument comme dans ton code initial
            nom_service = tool['function']['arguments'].get('nom_serveur', 'Inconnu')
            resultat = verifier_statut_serveur(nom_service)

            messages.append({
                'role': 'tool',
                'content': resultat,
                'name': nom_outil
            })

    # D : Réponse finale après analyse de l'outil
    reponse_finale = ollama.chat(model=modele, messages=messages)
    contenu = reponse_finale['message']['content']
    print(f"Agent (Post-Outil) : {contenu}")

    return contenu

if __name__ == "__main__":
    print("AGENT BIBOPS")
    contexte_it = "Tu es l'agent IA de support informatique Michelin. Utilise tes outils."

    lancer_agent(
        ticket_utilisateur="Impossible de me connecter au VPN ce matin.",
        contexte_systeme=contexte_it,
        outils_disponibles=[verifier_statut_serveur]
    )



# CHATGPT