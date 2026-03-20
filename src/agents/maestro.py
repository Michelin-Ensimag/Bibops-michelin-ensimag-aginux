import re
import ollama

from src.agents.memoire_courte import MemoCourTerme
from src.agents.outils import verifier_statut_serveur, chercher_documentation_technique, chercher_dans_kb

# = RCA =
# from src.llm_professor.rca_engine import RCAEngine
# rca = RCAEngine()

def lancer_agent(contexte,ticket_utilisateur, outils_disponibles, modele="phi3:latest"):

    memoire = MemoCourTerme(max_messages=50) # on a pas encore fait un analyse pour savoir la meilleur valeur du hyperparametre max_messages


    # systeme_prompt
    noms_outils = [outil.__name__ for outil in outils_disponibles]
    systeme_prompt = f"""Tu es l'agent IA de support informatique BibOps chez Michelin.
Contexte : {contexte}

PROCEDURE OBLIGATOIRE — suis ces etapes dans l'ordre :
1. Lis le ticket et extrait le mot-cle principal (exemples: "vpn", "bitlocker", "outlook", "imprimante").
2. Appelle l'outil le plus adapte avec ce mot-cle.
3. Apres avoir recu le resultat de l'outil, redige ta reponse finale en francais a l'utilisateur.

FORMAT STRICT pour appeler un outil — ecris UNIQUEMENT cette ligne, rien avant, rien apres :
ACTION: nom_outil("mot_cle")

OUTILS DISPONIBLES : {noms_outils}
INTERDIT : inventer un nom d'outil. INTERDIT : appeler deux fois le meme outil avec le meme argument.
INTERDIT : ecrire ACTION dans ta reponse finale.

Exemples corrects :
- Ticket "VPN ne marche pas" → ACTION: verifier_statut_serveur("VPN")
- Ticket "recuperer mot de passe Bitlocker" → ACTION: chercher_documentation_technique("bitlocker")
- Ticket "Outlook crash" → ACTION: chercher_dans_kb("outlook crash")
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

    # Suivi des appels déjà effectués pour éviter les doublons
    appels_deja_faits = set()

    # La Boucle de Réflexion (ReAct : Reason + Act) Max 5 itérations
    max_iterations = 5
    for etape in range(max_iterations):

        reponse = ollama.chat(model=modele, messages=messages_a_envoyer)
        contenu = reponse['message']['content']

        # Cherche si l'IA veut utiliser un outil (insensible à la casse : ACTION, Action, action...)
        match = re.search(r'(?i)action:\s*([a-zA-Z_]+)\("([^"]*)"', contenu)
        # Fallback pour guillemets simples
        if not match:
            match = re.search(r"(?i)action:\s*([a-zA-Z_]+)\('([^']*)'", contenu)

        # Si pas d'outil demandé, c'est la réponse finale ! On sort de la boucle.
        if not match:
            print(f"\n[Agent (Réponse Finale)] : \n{contenu}")
            memoire.add_message("assistant", contenu)
            return contenu

        # Si l'IA veut utiliser un outil
        nom_outil_demande = match.group(1)
        argument = match.group(2)

        print(f" [LLM veut utiliser l'outil] : {nom_outil_demande}('{argument}')")

        # Déduplication : éviter de rappeler le même outil avec le même argument
        cle_appel = (nom_outil_demande, argument.lower().strip())
        if cle_appel in appels_deja_faits:
            dedup_msg = (
                f"STOP. Tu as déjà appelé '{nom_outil_demande}(\"{argument}\")' et obtenu un résultat. "
                f"N'appelle PLUS aucun outil. Rédige maintenant ta réponse finale à l'utilisateur "
                f"en utilisant uniquement les résultats déjà obtenus."
            )
            messages_a_envoyer.append({'role': 'assistant', 'content': contenu})
            messages_a_envoyer.append({'role': 'user', 'content': dedup_msg})
            continue
        appels_deja_faits.add(cle_appel)

        noms_valides = [o.__name__ for o in outils_disponibles]
        resultat_outil = f"Erreur : L'outil '{nom_outil_demande}' n'existe pas. Les seuls outils disponibles sont : {noms_valides}. Utilise UNIQUEMENT un de ces outils."

        # Exécution de l'outil
        for outil in outils_disponibles:
            if outil.__name__ == nom_outil_demande:
                resultat_outil = outil(argument)
                break

        print(f"   -> Résultat : {str(resultat_outil)[:150]}...")

        # 3. On ajoute la pensée de l'IA et le résultat de l'outil dans l'historique
        # pour relancer la boucle et qu'elle analyse le résultat
        messages_a_envoyer.append({'role': 'assistant', 'content': contenu})
        messages_a_envoyer.append({'role': 'user', 'content': f"Résultat de l'outil : {resultat_outil}"})

    # Si on dépasse les 5 itérations
    reponse_secours = "Je n'ai pas pu résoudre le problème dans le temps imparti. Merci de contacter le support de niveau 2."
    print(f"\n[Agent (Timeout)] : {reponse_secours}")
    return reponse_secours

if __name__ == "__main__":
    print("[ AGENT BIBOPS ]")

    mes_outils = [verifier_statut_serveur, chercher_documentation_technique,chercher_dans_kb]

    lancer_agent("L'entreprise est Michelin. Le VPN principal est Cisco.","Impossible de me connecter au VPN ce matin.", outils_disponibles=mes_outils)
    print("\n" + "="*50)
    lancer_agent("L'entreprise est Michelin. Le VPN principal est Cisco.","Comment récupérer mon mot de passe Bitlocker ?", outils_disponibles=mes_outils)
