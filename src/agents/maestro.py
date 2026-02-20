import ollama
from outils import verifier_statut_serveur

contexte_entreprise = "L'entreprise est Michelin. Le VPN principal est Cisco."
system_prompt = f"""
Tu es l'agent IA de support informatique (BibOps). 
Contexte actuel : {contexte_entreprise}

Règles :
1. Si l'utilisateur a un problème avec un service, utilise TOUJOURS l'outil 'verifier_statut_serveur' avant de répondre.
2. Sois concis et professionnel.
"""

def lancer_agent(ticket_utilisateur, modele="llama3.2:1b"):
    print(f"\n👤 Utilisateur : {ticket_utilisateur}")

    messages = [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': ticket_utilisateur}
    ]

    # ÉTAPE A : L'agent réfléchit avec son outil
    reponse = ollama.chat(
        model=modele,
        messages=messages,
        tools=[verifier_statut_serveur] # On transmet la fonction importée
    )

    messages.append(reponse['message'])

    # ÉTAPE B : L'agent a-t-il appelé l'outil ?
    if not reponse['message'].get('tool_calls'):
        contenu_direct = reponse['message']['content']
        print(f"Agent (Direct) : {contenu_direct}")
        return contenu_direct

    # ÉTAPE C : Exécution de l'outil
    for tool in reponse['message']['tool_calls']:
        if tool['function']['name'] == 'verifier_statut_serveur':
            # Extraction de l'argument trouvé par l'IA
            nom_service = tool['function']['arguments'].get('nom_serveur', 'Inconnu')

            # Appel de la fonction Python
            resultat = verifier_statut_serveur(nom_service)

            # Renvoi du résultat à l'IA
            messages.append({
                'role': 'tool',
                'content': resultat,
                'name': 'verifier_statut_serveur'
            })

    # ÉTAPE D : Réponse finale après analyse de l'outil
    reponse_finale = ollama.chat(model=modele, messages=messages)
    contenu = reponse_finale['message']['content']
    print(f"Agent (Post-Outil) : {contenu}")

    return contenu


# --- ZONE DE TEST DIRECT ---
if __name__ == "__main__":
    print("=== DÉMO AGENT BIBOPS ===")
    lancer_agent("Impossible de me connecter au VPN ce matin.")
    lancer_agent("Mon Outlook crash au démarrage, le serveur mail est cassé ?")