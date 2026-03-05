import sys
import os
from memoire_courte import ShortTermMemory
import ollama
from src.agents.outils import verifier_statut_serveur
from src.agents.rca_engine import RCAEngine

# Permet d'importer correctement les autres fichiers du dossier
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))



rca = RCAEngine()
memoire = ShortTermMemory(max_messages=6) # Instanciation de la mémoire

contexte_entreprise = "L'entreprise est Michelin. Le VPN principal est Cisco."

# INTEGRATION CONCEPT : CHAIN OF THOUGHT (Tiré de chaine_de_pensee.py)
contexte_generale = f"""
Tu es l'agent IA de support informatique (BibOps). 
Contexte actuel : {contexte_entreprise}

Règles :
1. Pense étape par étape (Chain of Thought) avant de formuler ta réponse finale.
2. Si l'utilisateur a un problème avec un service, utilise TOUJOURS l'outil 'verifier_statut_serveur'.
3. Sois concis et professionnel.
"""

def lancer_agent(ticket_utilisateur, outils_disponibles, modele="phi3:latest"):
    print(f"\n👤 Utilisateur : {ticket_utilisateur}")

    # Ajout du message utilisateur dans la mémoire à court terme
    memoire.add_message("user", ticket_utilisateur)

    print(f"[RCA] Analyse technique du ticket...")
    diagnostic = rca.analyser_cause_racine(ticket_utilisateur)

    # On construit le System Prompt complet avec le RCA
    system_prompt = f"{contexte_generale}\n\nDiagnostic RCA : {diagnostic}"

    # On prépare la liste de messages : Le System Prompt + TOUTE LA MEMOIRE RECENTE
    messages_a_envoyer = [{'role': 'system', 'content': system_prompt}] + memoire.get_messages()

    # Appel à Ollama
    reponse = ollama.chat(
        model=modele,
        messages=messages_a_envoyer,
        tools=outils_disponibles
    )

    # B : L'agent a-t-il appelé l'outil ?
    if not reponse['message'].get('tool_calls'):
        contenu_direct = reponse['message']['content']
        print(f"🤖 Agent (Direct) : {contenu_direct}")
        memoire.add_message("assistant", contenu_direct) # On sauvegarde la réponse de l'IA
        return contenu_direct

    # C : Exécution de l'outil
    messages_a_envoyer.append(reponse['message']) # On garde trace de l'appel d'outil

    for tool in reponse['message']['tool_calls']:
        nom_outil = tool['function']['name']
        if nom_outil == 'verifier_statut_serveur':
            nom_service = tool['function']['arguments'].get('nom_serveur', 'Inconnu')
            resultat = verifier_statut_serveur(nom_service)
            messages_a_envoyer.append({'role': 'tool', 'content': resultat, 'name': nom_outil})

    # D : Réponse finale après outil
    reponse_finale = ollama.chat(model=modele, messages=messages_a_envoyer)
    contenu = reponse_finale['message']['content']

    print(f"🤖 Agent (Post-Outil) : {contenu}")
    memoire.add_message("assistant", contenu) # Mémorisation de la réponse finale
    return contenu

if __name__ == "__main__":
    print("=== AGENT BIBOPS AVEC MEMOIRE ET RCA ===")
    # Simulation d'une conversation multi-tours grâce à la mémoire !
    lancer_agent("Impossible de me connecter au VPN ce matin.", [verifier_statut_serveur])
    lancer_agent("C'est quoi l'adresse du serveur de secours ?", [verifier_statut_serveur])