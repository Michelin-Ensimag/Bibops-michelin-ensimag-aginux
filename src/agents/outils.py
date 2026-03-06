import json
import sqlite3
import os
import chromadb

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
DB_PATH = os.path.join(BASE_DIR, 'data', 'bibops.db')
CHROMA_PATH = os.path.join(BASE_DIR, 'data', 'vectordb')


def verifier_statut_serveur(nom_serveur: str) -> str:
    """Vérifie l'état d'un serveur dans la base de données SQLite."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT statut FROM serveurs_it WHERE nom = ?", (nom_serveur.upper(),))
        resultat = cursor.fetchone()
        conn.close()

        if resultat:
            return f"Statut : Le service {nom_serveur} est {resultat[0]}."
        return f"Service inconnu : Aucun serveur nommé {nom_serveur}."
    except Exception as e:
        return f"Erreur SQL : {e}"


def chercher_dans_kb(requete: str) -> str:
    """
    Recherche des solutions dans la Knowledge Base pour un problème IT.
    Args:
        requete: Description du problème à rechercher (ex: 'vpn ne marche pas', 'outlook crash').
    """
    print(f"\n[ACTION OUTIL] -> Recherche dans la KB pour : '{requete}'...")
    kb_path = os.path.join(BASE_DIR, 'data', 'knowedge_base.json')
    try:
        with open(kb_path, "r", encoding="utf-8") as f:
            kb = json.load(f)["knowledge_base"]
    except FileNotFoundError:
        return "ERREUR : Knowledge Base introuvable."
    except json.JSONDecodeError:
        return "ERREUR : Knowledge Base corrompue."

    requete_lower = requete.lower()
    resultats = []

    for entry in kb:
        score = 0
        for mot in entry["mots_cles"]:
            if mot.lower() in requete_lower:
                score += 2
        for mot in requete_lower.split():
            if mot in entry["probleme"].lower():
                score += 1
                break
        if score > 0:
            resultats.append((score, entry))

    resultats.sort(key=lambda x: x[0], reverse=True)
    resultats = resultats[:3]

    if not resultats:
        return f"Aucune solution trouvée pour '{requete}'. Recommandation : créer un ticket support."

    reponse = f"{len(resultats)} solution(s) trouvée(s) :\n\n"
    for idx, (score, entry) in enumerate(resultats, 1):
        reponse += f"--- SOLUTION {idx} ---\nProblème : {entry['probleme']}\nCatégorie : {entry['categorie']}\nPriorité : {entry['priorite']}\n\n"
        if entry["solution"].get("diagnostic"):
            reponse += "DIAGNOSTIC :\n"
            for step in entry["solution"]["diagnostic"]:
                reponse += f"  - {step}\n"
            reponse += "\n"
        reponse += "RÉSOLUTION :\n"
        for i, step in enumerate(entry["solution"]["resolution"], 1):
            reponse += f"  {i}. {step}\n"
        reponse += "\n"
        if entry["solution"].get("escalade"):
            reponse += f"ESCALADE : {entry['solution']['escalade']}\n\n"

    return reponse


def chercher_documentation_technique(mot_cle: str) -> str:
    """Cherche dans la documentation technique vectorielle de Michelin une procédure de résolution."""
    try:
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        collection = client.get_collection(name="doc_michelin")

        resultats = collection.query(query_texts=[mot_cle], n_results=1)

        # Vérifier si on a vraiment trouvé quelque chose
        if not resultats['documents'] or not resultats['documents'][0]:
            return f"Aucune documentation trouvée pour : {mot_cle}"

        doc_trouve = resultats['documents'][0][0]
        kb_id = resultats['ids'][0][0]

        return f"Documentation trouvée (Source: {kb_id}) :\n{doc_trouve}"
    except Exception as e:
        return f"Aucune documentation trouvée. Erreur: {e}"