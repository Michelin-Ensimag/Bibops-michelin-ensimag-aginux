import json
import os
import ollama

# ==========================================
# CONFIGURATION DES CHEMINS
# ==========================================
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
INPUT_JSON = os.path.join(BASE_DIR, 'data', 'tickets_evalues.json')
OUTPUT_JSON = os.path.join(BASE_DIR, 'data', 'tickets_notes.json')

def evaluer_reponses(model_juge="llama3.2:1b"):
    print(f"⚖️ Démarrage du LLM-Inspector avec le Juge : {model_juge}\n")

    # 1. Vérifier que les réponses existent
    if not os.path.exists(INPUT_JSON):
        print(f"❌ Erreur : Le fichier {INPUT_JSON} est introuvable. Lancez le benchmark d'abord !")
        return

    # 2. Lecture du fichier généré précédemment
    with open(INPUT_JSON, 'r', encoding='utf-8') as file:
        tickets = json.load(file)

    # 3. Évaluation ticket par ticket
    for ticket in tickets:
        print(f"🔍 Évaluation du ticket #{ticket['id_ticket']}...")

        # Le prompt ultra-directif pour le Juge
        prompt_juge = f"""
        Tu es un inspecteur qualité (LLM-as-a-Judge) strict et impartial.
        Voici le problème initial de l'utilisateur : "{ticket['ticket']}"
        Voici la réponse apportée par le modèle testé : "{ticket['reponse']}"

        Évalue cette réponse sur une échelle de 1 à 10.
        Critères : pertinence par rapport au problème, clarté et concision.
        
        Réponds UNIQUEMENT au format JSON avec exactement deux clés : 
        "note" (un nombre entier entre 1 et 10) et 
        "justification" (une très courte phrase expliquant ta note).
        """

        try:
            # ⚠️ L'ASTUCE PRO : on force le format JSON
            reponse_juge = ollama.chat(
                model=model_juge,
                messages=[{'role': 'user', 'content': prompt_juge}],
                format='json'
            )

            # 4. Extraction de la note
            texte_brut = reponse_juge['message']['content']
            resultat_json = json.loads(texte_brut) # On convertit le texte de l'IA en dictionnaire Python

            # Sauvegarde des notes dans notre dictionnaire
            ticket['note_sur_10'] = resultat_json.get('note', 0)
            ticket['justification_juge'] = resultat_json.get('justification', "Aucune justification donnée.")

            print(f"   ⭐ Note attribuée : {ticket['note_sur_10']}/10")
            print(f"   💬 Avis : {ticket['justification_juge']}")

        except Exception as e:
            print(f"   ❌ Erreur lors de l'évaluation par l'IA : {e}")
            ticket['note_sur_10'] = None
            ticket['justification_juge'] = "Erreur technique du juge."

    # 5. Sauvegarde du fichier final
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f_out:
        json.dump(tickets, f_out, indent=4, ensure_ascii=False)

    print("-" * 50)
    print(f"✅ Évaluation terminée ! Le bulletin de notes est généré dans : {OUTPUT_JSON}")

# ==========================================
# LANCEMENT
# ==========================================
if __name__ == "__main__":
    # Idéalement, le modèle "Juge" devrait être plus gros que le modèle évalué (ex: Llama 3 8B pour évaluer un 1B).
    # Mais pour tester sur ton Mac, le 1B fera l'affaire !
    evaluer_reponses(model_juge="llama3.2:1b")