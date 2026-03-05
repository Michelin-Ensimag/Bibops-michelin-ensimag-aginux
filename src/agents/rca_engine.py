# CHATGPT


import ollama

class RCAEngine:
    def __init__(self, model="phi3:latest"):
        self.model = model

    def analyser_cause_racine(self, ticket):
        """
        Analyse le ticket pour déterminer la cause technique réelle.
        """
        prompt = f"""
        Tu es l'analyste de cause racine (RCA) du support IT.
        
        INSTRUCTIONS DE TRAVAIL :
        1. Analyse les faits techniques présents dans le TICKET.
        2. Compare ces faits avec la LISTE DES SERVICES connus.
        3. Sélectionne uniquement le service dont les caractéristiques correspondent aux symptômes.
        
        LISTE DES SERVICES :
        - VPN : Connexion à distance, accès domicile, tunnel sécurisé.
        - CISCO : Commutateurs, routeurs, infrastructure physique.
        - Outlook : Courriels, calendrier, archives mails.
        
        TICKET : "{ticket}"
        
        FORMAT DE SORTIE :
        CAUSE : <Deduction logique>
        MOT-CLÉ : <Nom du service sélectionné uniquement>
        """

        try:
            response = ollama.chat(model=self.model, messages=[
                {'role': 'system', 'content': 'Tu es un module de Root Cause Analysis.'},
                {'role': 'user', 'content': prompt}
            ])
            full_content = response['message']['content']

            # --- PETIT NETTOYAGE (Post-processing) ---
            # On ne garde que les lignes qui contiennent CAUSE ou MOT-CLÉ
            lines = [l for l in full_content.split('\n') if "CAUSE" in l.upper() or "MOT-CLÉ" in l.upper() or "MOT-CLE" in l.upper()]
            clean_diag = "\n".join(lines)

            return clean_diag if clean_diag else full_content
        except Exception as e:
            return f"Erreur diagnostic : {str(e)}"

if __name__ == "__main__":
    engine = RCAEngine()
    test_ticket = "Impossible de me connecter au VPN ce matin"
    print("Voici l'analyse du ticket :")
    print(engine.analyser_cause_racine(test_ticket))







# CHATGPT