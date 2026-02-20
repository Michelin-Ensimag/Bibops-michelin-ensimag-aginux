import ollama
from outils import verifier_statut_serveur

# Je pense que ca serait mieux de creer un autre fichier l appeler
# peut etre memoire_long  pour y mettre le contexte generale
# et un autre memoire_court_terme pour mettre le contexte
# qui concerne juste la requete actuelle

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

    messages = [
        {'role': 'system', 'content': contexte_generale},
        {'role': 'user', 'content': ticket_utilisateur}
    ]

    # A : L'agent réfléchit avec son outil
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

    # C : Exécution de l'outil ( on doit l ajuster pour s adapter a dautres roles ... )
    for tool in reponse['message']['tool_calls']:
        nom_outil = tool['function']['name']

        if nom_outil == 'verifier_statut_serveur':
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
