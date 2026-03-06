import sys
import os
import re
import ollama

# Permet d'importer correctement les autres fichiers du dossier
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.agents.memoire_courte import MemoCourTerme
from src.agents.serveur_mcp import verifier_statut_serveur, chercher_documentation_technique

# = RCA =
# from src.llm_professor.rca_engine import RCAEngine
# rca = RCAEngine()

memoire = MemoCourTerme(max_messages=50) # on a pas encore fait un analyse pour savoir la meilleur valeur du hyperparametre max_messages

def lancer_agent(contexte,ticket_utilisateur, outils_disponibles, modele="phi3:latest"):

    # systeme_prompt
    systeme_prompt = f"""
    Tu es l'agent IA de support informatique (BibOps). 
    Contexte actuel : {contexte}
    
    Règles :
    1. Pense étape par étape (Chain of Thought).
    2. Si tu as besoin d'une information, utilise un des outils qui te sont fournis ci-dessous.
    3. Pour utiliser un outil, écris EXACTEMENT et UNIQUEMENT sur une ligne : ACTION: nom_de_l_outil("argument")
    4. Une fois que tu as le résultat de l'outil, formule ta réponse finale de manière concise et professionnelle.
    """


    print(f"\n [Utilisateur] : {ticket_utilisateur}")
    memoire.add_message("user", ticket_utilisateur)

    diagnostic_texte = ""

    # = RCA =
    # print(f"[RCA] Analyse technique du ticket...")
    # diagnostic = rca.analyser_cause_racine(ticket_utilisateur)
    # diagnostic_texte = f"\n\n[ANALYSE TECHNIQUE RCA]\n{diagnostic}"

    # 1. Préparation dynamique de la liste des outils
    description_outils = "\nOUTILS DISPONIBLES :\n"
    for outil in outils_disponibles:
        description_outils += f"- {outil.__name__} : {outil.__doc__}\n"

    # 2. Assemblage du prompt (la variable diagnostic_texte sera vide si le RCA est commenté)
    system_prompt = f"{systeme_prompt}\n{description_outils}{diagnostic_texte}"

    messages_a_envoyer = [{'role': 'system', 'content': system_prompt}] + memoire.get_messages()

    # 3. Premier Appel à Ollama (L'IA réfléchit et choisit un outil)
    reponse = ollama.chat(model=modele, messages=messages_a_envoyer)
    contenu = reponse['message']['content']

    # 4. Capture de l'outil demandé via Regex
    match = re.search(r'ACTION:\s*([a-zA-Z_]+)\(["\']?([^"\'\)]+)["\']?\)', contenu)

    # Si l'IA ne demande pas d'outil, c'est qu'elle a sa réponse directe
    if not match:
        print(f"[Agent (content)] : {contenu}")
        memoire.add_message("assistant", contenu)
        return contenu

    # 5. Exécution de l'outil
    nom_outil_demande = match.group(1)
    argument = match.group(2)

    print(f"[LLM veut utiliser] : {nom_outil_demande}('{argument}')")
    resultat_outil = f"Erreur : L'outil '{nom_outil_demande}' n'existe pas."

    for outil in outils_disponibles:
        if outil.__name__ == nom_outil_demande:
            resultat_outil = outil(argument)
            break

    print(f"   -> Résultat : {resultat_outil[:100]}...")

    # 6. On injecte le résultat dans la conversation
    messages_a_envoyer.append({'role': 'assistant', 'content': contenu})
    messages_a_envoyer.append({'role': 'user', 'content': f"Résultat de l'outil : {resultat_outil}"})

    # 7. Appel final pour formuler la réponse à l'utilisateur
    reponse_finale = ollama.chat(model=modele, messages=messages_a_envoyer)
    contenu_final = reponse_finale['message']['content']

    print(f"\n[Agent (outil)]: \n{contenu_final}")
    memoire.add_message("assistant", contenu_final)

    return contenu_final

if __name__ == "__main__":
    print("[ AGENT BIBOPS ]")

    mes_outils = [verifier_statut_serveur, chercher_documentation_technique]

    lancer_agent("L'entreprise est Michelin. Le VPN principal est Cisco.","Impossible de me connecter au VPN ce matin.", outils_disponibles=mes_outils)
    print("\n" + "="*50)
    lancer_agent("L'entreprise est Michelin. Le VPN principal est Cisco.","Comment récupérer mon mot de passe Bitlocker ?", outils_disponibles=mes_outils)