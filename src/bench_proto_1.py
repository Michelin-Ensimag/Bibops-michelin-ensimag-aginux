import requests
import time

def tester_support_it(ticket_client, model="llama3.2:1b"):
    url = "http://localhost:11434/api/generate"
    
    payload = {
        "model": model,
        "prompt": f"Tu es un technicien support IT. Résous ce problème : {ticket_client}",
        "stream": False
    }

    print(f"\nModèle utilisé: {model} ---")
    start_time = time.time() 

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        
        # Calcul 
        resultat = response.json()
        fin_time = time.time() - start_time
        
        print(f"réponse :\n{resultat['response']}")
        print(f"\ntemps de réponse : {fin_time:.2f} secondes")
        
    except Exception as e:
        print(f"ERREUR : Impossible de contacter Ollama ({e})")

if __name__ == "__main__":
    print("PROTOTYPE 1 BIBOPS - Support IT")
    ticket = input("Entrez un ticket IT : ")
    tester_support_it(ticket)