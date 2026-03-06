import json
import sqlite3
import os
import chromadb

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
DB_PATH = os.path.join(BASE_DIR, 'data', 'databases', 'bibops.db')
CHROMA_PATH = os.path.join(BASE_DIR, 'data', 'databases', 'vectordb')

# Initialisé une seule fois au niveau du module
_chroma_client = None
def _get_chroma_collection():
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    return _chroma_client.get_collection(name="doc_michelin")


def verifier_statut_serveur(nom_serveur: str) -> str:
    """Vérifie l'état d'un serveur dans la base de données SQLite."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            # Recherche exacte d'abord
            cursor.execute("SELECT nom, statut FROM serveurs_it WHERE nom = ?", (nom_serveur.upper(),))
            resultat = cursor.fetchone()

            # Si pas de match exact, recherche partielle (ex: "Cisco VPN" ou "Cisco_VPN" -> trouve "VPN" et "CISCO")
            if not resultat:
                mots = nom_serveur.upper().replace('_', ' ').split()
                placeholders = " OR ".join(["nom = ?" for _ in mots])
                cursor.execute(f"SELECT nom, statut FROM serveurs_it WHERE {placeholders}", mots)
                resultats = cursor.fetchall()
                if resultats:
                    lignes = [f"- {nom} : {statut}" for nom, statut in resultats]
                    return f"Services correspondants :\n" + "\n".join(lignes)
                return f"Service inconnu : Aucun serveur nommé {nom_serveur}."

        return f"Statut : Le service {resultat[0]} est {resultat[1]}."
    except Exception as e:
        return f"Erreur SQL : {e}"


def chercher_dans_kb(requete: str) -> str:
    """
        Utilise CET outil pour chercher des solutions basiques (mots clés) dans la base de connaissances classique (JSON).
        """
    print(f"\n[ACTION OUTIL] -> Recherche dans la KB pour : '{requete}'...")
    kb_path = os.path.join(BASE_DIR, 'data', 'knowledge_base', 'knowledge_base.json')
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
    """
    Utilise CET outil pour chercher des procédures techniques longues ou des tutoriels détaillés (Bitlocker, VPN) dans les articles officiels Michelin (Vector DB).
    """
    try:
        collection = _get_chroma_collection()

        resultats = collection.query(query_texts=[mot_cle], n_results=1, include=["documents", "distances"])

        # Vérifier si on a vraiment trouvé quelque chose
        if not resultats['documents'] or not resultats['documents'][0]:
            return f"Aucune documentation trouvée pour : {mot_cle}"

        # Filtrage par pertinence : rejeter les résultats trop éloignés (distance cosine >= 1.2)
        distance = resultats['distances'][0][0]
        if distance >= 1.2:
            return f"Aucune documentation pertinente trouvée pour : {mot_cle} (meilleur résultat trop éloigné)."

        doc_trouve = resultats['documents'][0][0]
        kb_id = resultats['ids'][0][0]

        return f"Documentation trouvée (Source: {kb_id}, pertinence: {distance:.2f}) :\n{doc_trouve}"
    except Exception as e:
        return f"Aucune documentation trouvée. Erreur: {e}"