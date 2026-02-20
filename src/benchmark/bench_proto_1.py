# CHATGPT
import requests
import time

def tester_support_it(ticket_client, model="llama3.2:1b"):
    url = "http://localhost:11434/api/generate"
    
    contexte = { # Ce format est un dictionnaire Python qui sera converti en JSON pour l'API REST d'Ollama via requests.post(url, json=contexte)
        "model": model,
        "prompt": f"Tu es un technicien support IT. Résous ce problème : {ticket_client}",
        "stream": False # stream: False signifie que la réponse complète sera reçue en une seule requête , Si stream: True, la réponse arriverait par chunks (morceaux) au fil du temps, utile pour afficher les tokens générés progressivement
    }

    print(f"\nModèle utilisé: {model} ---")
    start_time = time.time() 

    response = requests.post(url, json=contexte)
    response.raise_for_status()

    # Calcul
    resultat = response.json()
    fin_time = time.time() - start_time

    print(f"réponse :\n{resultat['response']}") # l'option sans specifier response produit une longue chaine de characteres qui melange notre reponse a d autres truc que je pense comme le temps d execution , c est pour ca qu au lieu d executer la lib request , on peut directement utiliser ces infos la pour avoir le temps d execution
    print(f"\ntemps de réponse : {fin_time:.2f} secondes")

if __name__ == "__main__":
    print("PROTOTYPE 1 BIBOPS - Support IT")
    ticket = input("Entrez un ticket IT : ")
    tester_support_it(ticket)
# CHATGPT