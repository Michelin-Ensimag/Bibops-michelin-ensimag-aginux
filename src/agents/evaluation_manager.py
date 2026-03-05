# CHATGPT



import json
import os
from datetime import datetime

def sauvegarder_evaluation(ticket, diagnostic, reponse, note):
    file_name = "feedback_log.json"
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ticket": ticket,
        "rca_diag": diagnostic,
        "agent_output": reponse,
        "score": "UTILE" if note == "1" else "INUTILE"
    }

    data = []
    # On lit l'existant pour ajouter à la liste
    if os.path.exists(file_name):
        with open(file_name, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except: data = []

    data.append(entry)
    with open(file_name, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    print(f"\n[SYSTÈME] Feedback enregistré dans {file_name}")



#CHATGPT