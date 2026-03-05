import sys
import os
import re
import ollama

# Permet d'importer correctement les autres fichiers du dossier
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.agents.memoire_courte import ShortTermMemory
from src.agents.rca_engine import RCAEngine
from src.agents.serveur_mcp import verifier_statut_serveur, chercher_documentation_technique

rca = RCAEngine()
memoire = ShortTermMemory(max_messages=6)

contexte_entreprise = "L'entreprise est Michelin. Le VPN principal est Cisco."

# 1. LE PROMPT DE BASE (On ne hardcode plus les outils ici !)
contexte_base = f"""
Tu es l'agent IA de support informatique (BibOps). 
Contexte actuel : {contexte_entreprise}

Règles :
1. Pense étape par étape (Chain of Thought).
2. Si tu as besoin d'une information, utilise un des outils qui te sont fournis ci-dessous.
3. Pour utiliser un outil, écris EXACTEMENT et UNIQUEMENT sur une ligne : ACTION: nom_de_l_outil("argument")
4. Une fois que tu as le résultat de l'outil, formule ta réponse finale de manière concise et professionnelle.
"""

def lancer_agent(ticket_utilisateur, outils_disponibles, modele="phi3:latest"):
    print(f"\n👤 Utilisateur : {ticket_utilisateur}")
    memoire.add_message("user", ticket_utilisateur)

    print(f"[RCA] Analyse technique du ticket...")
    diagnostic = rca.analyser_cause_racine(ticket_utilisateur)


    # On parcourt la liste des outils fournis et on lit leur nom et documentation

    description_outils = "\nOUTILS DISPONIBLES :\n"
    for outil in outils_disponibles:
        # tool.__name__ récupère le nom de la fonction (ex: verifier_statut_serveur)
        # tool.__doc__ récupère les commentaires sous le def de la fonction
        description_outils += f"- {outil.__name__} : {outil.__doc__}\n"

    # On assemble le grand prompt final
    system_prompt = f"{contexte_base}\n{description_outils}\nDiagnostic RCA : {diagnostic}"

    messages_a_envoyer = [{'role': 'system', 'content': system_prompt}] + memoire.get_messages()

    # Premier Appel à Ollama
    reponse = ollama.chat(model=modele, messages=messages_a_envoyer)
    contenu = reponse['message']['content']

    # 2. REGEX GÉNÉRIQUE : Elle capture n'importe quel nom d'outil et son argument !
    match = re.search(r'ACTION:\s*([a-zA-Z_]+)\(["\']?([^"\'\)]+)["\']?\)', contenu)

    if not match:
        print(f"🤖 Agent (Direct) : {contenu}")
        memoire.add_message("assistant", contenu)
        return contenu

    # 3. EXÉCUTION DYNAMIQUE
    nom_outil_demande = match.group(1) # Ex: chercher_documentation_technique
    argument = match.group(2)          # Ex: Bitlocker

    print(f"🛠️ L'IA veut utiliser : {nom_outil_demande}('{argument}')")

    resultat_outil = f"Erreur : L'outil '{nom_outil_demande}' n'existe pas."

    # On cherche l'outil demandé dans notre liste d'outils disponibles
    for outil in outils_disponibles:
        if outil.__name__ == nom_outil_demande:
            resultat_outil = outil(argument) # On exécute la fonction !
            break

    print(f"   -> Résultat : {resultat_outil[:100]}...") # Affiche les 100 premiers caractères

    # On ajoute la réflexion de l'IA et la réponse de l'outil au contexte
    messages_a_envoyer.append({'role': 'assistant', 'content': contenu})
    messages_a_envoyer.append({'role': 'user', 'content': f"Résultat de l'outil : {resultat_outil}"})

    # D : Réponse finale après avoir lu le résultat de l'outil
    reponse_finale = ollama.chat(model=modele, messages=messages_a_envoyer)
    contenu_final = reponse_finale['message']['content']

    print(f"\n🤖 Agent (Post-Outil) : \n{contenu_final}")
    memoire.add_message("assistant", contenu_final)
    return contenu_final

if __name__ == "__main__":
    print("=== AGENT BIBOPS (ROUTAGE DYNAMIQUE) ===")

    # On liste simplement les outils disponibles pour cette session
    mes_outils = [verifier_statut_serveur, chercher_documentation_technique]

    # Test 1 : L'agent devrait choisir tout seul l'outil SQL (verifier_statut_serveur)
    lancer_agent("Impossible de me connecter au VPN ce matin.", outils_disponibles=mes_outils)

    print("\n" + "="*50)

    # Test 2 : L'agent devrait choisir tout seul l'outil RAG (chercher_documentation_technique)
    lancer_agent("Comment récupérer mon mot de passe Bitlocker ?", outils_disponibles=mes_outils)

    print("\n" + "="*50)
    lancer_agent("Comment récupérer mon mot de passe Bitlocker ?", [chercher_documentation_technique])