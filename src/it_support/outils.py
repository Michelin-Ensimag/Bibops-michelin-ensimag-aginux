import json
import sqlite3
import os
import re
from dataclasses import dataclass, asdict
from typing import Any

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
DB_PATH = os.path.join(BASE_DIR, 'data', 'databases', 'bibops.db')
CHROMA_PATH = os.path.join(BASE_DIR, 'data', 'databases', 'vectordb')





@dataclass(frozen=True) # frozen pour rendre les instances immuables, ce qui est une bonne pratique pour les configurations
class ToolPolicy:
    timeout_s: float
    max_retries: int
    min_arg_len: int
    max_arg_len: int


TOOL_POLICIES: dict[str, ToolPolicy] = {
    "verifier_statut_serveur": ToolPolicy(timeout_s=3.0, max_retries=0, min_arg_len=2, max_arg_len=64),
    "chercher_documentation_technique": ToolPolicy(timeout_s=8.0, max_retries=1, min_arg_len=2, max_arg_len=120),
    "chercher_dans_kb": ToolPolicy(timeout_s=5.0, max_retries=1, min_arg_len=2, max_arg_len=120),
}

RAG_DISTANCE_MAX = 1.2 # dans les distances de ChromaDB, plus c'est petit, plus c'est pertinent; au-delà de 1.2, on considère que le document est trop éloigné pour être utile
RAG_N_RESULTS_PER_QUERY = 3 # nombre de résultats à récupérer pour chaque variante de la requête avant le reranking; on peut ajuster pour trouver un bon équilibre entre diversité et pertinence
RAG_MAX_CITATIONS = 3 # nombre maximum de citations à inclure dans la réponse finale pour éviter de submerger l'utilisateur avec trop d'informations, même si plus de résultats sont pertinents


import chromadb
_chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
_chroma_client.get_collection(name="doc_michelin")


def get_tool_policy(tool_name: str) -> ToolPolicy:
    return TOOL_POLICIES.get(tool_name, ToolPolicy(timeout_s=5.0, max_retries=0, min_arg_len=1, max_arg_len=120))


def get_tool_policies() -> dict[str, dict[str, Any]]:
    return {name: asdict(policy) for name, policy in TOOL_POLICIES.items()}


def normaliser_argument_outil(tool_name: str, argument: str) -> str:
    arg = (argument or "").strip() # on enlève les espaces au début et à la fin
    policy = get_tool_policy(tool_name)

    if len(arg) < policy.min_arg_len:
        raise ValueError(f"argument trop court (< {policy.min_arg_len})")
    if len(arg) > policy.max_arg_len:
        raise ValueError(f"argument trop long (> {policy.max_arg_len})")

    if tool_name == "verifier_statut_serveur":
        cleaned = " ".join(arg.replace("_", " ").split())
        return cleaned.upper()

    return " ".join(arg.split())


def _tokenize_query(text: str) -> list[str]:
    return [tok for tok in re.findall(r"[a-zA-Z0-9]+", text.lower()) if len(tok) >= 3]


def _generate_query_variants(query: str) -> list[str]:
    normalized = " ".join(query.split())
    if not normalized:
        return []

    variants = [normalized]
    tokens = _tokenize_query(normalized)
    if len(tokens) > 1:
        variants.append(" ".join(tokens))
    if len(tokens) > 2:
        variants.append(" ".join(tokens[:2]))
    if tokens:
        variants.append(tokens[0])

    # Conserve l'ordre d'apparition en supprimant les doublons.
    seen = set()
    unique = []
    for variant in variants:
        if variant not in seen:
            unique.append(variant)
            seen.add(variant)
    return unique


def _lexical_overlap_score(query: str, document: str) -> float:
    q_tokens = set(_tokenize_query(query))
    if not q_tokens:
        return 0.0

    doc_tokens = set(_tokenize_query(document[:2500]))
    if not doc_tokens:
        return 0.0

    overlap = q_tokens.intersection(doc_tokens)
    return len(overlap) / len(q_tokens)


def _rerank_hybrid_candidates(query: str, raw_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}

    for result in raw_results:
        ids = result.get("ids") or []
        documents = result.get("documents") or []
        distances = result.get("distances") or []
        if not ids or not documents:
            continue

        doc_ids = ids[0] if isinstance(ids[0], list) else ids
        doc_texts = documents[0] if isinstance(documents[0], list) else documents
        doc_distances = distances[0] if distances and isinstance(distances[0], list) else distances

        for idx, doc_id in enumerate(doc_ids):
            doc_text = doc_texts[idx] if idx < len(doc_texts) else ""
            distance = doc_distances[idx] if idx < len(doc_distances) else None
            if distance is None:
                continue

            lexical = _lexical_overlap_score(query, doc_text)
            vector_score = 1.0 / (1.0 + float(distance))
            hybrid_score = (0.75 * vector_score) + (0.25 * lexical)

            current = by_id.get(doc_id)
            candidate = {
                "id": doc_id,
                "document": doc_text,
                "distance": float(distance),
                "lexical_score": round(lexical, 4),
                "hybrid_score": round(hybrid_score, 4),
            }
            if current is None or candidate["hybrid_score"] > current["hybrid_score"]:
                by_id[doc_id] = candidate

    ordered = sorted(by_id.values(), key=lambda c: c["hybrid_score"], reverse=True)
    filtered = [
        cand
        for cand in ordered
        if cand["distance"] < RAG_DISTANCE_MAX or cand["lexical_score"] >= 0.25
    ]
    return filtered[:RAG_MAX_CITATIONS]


def _extract_snippet(document: str, max_chars: int = 220) -> str:
    one_line = " ".join(document.replace("\n", " ").split())
    if len(one_line) <= max_chars:
        return one_line
    return one_line[: max_chars - 3] + "..."


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
        query = " ".join((mot_cle or "").split())
        if not query:
            return "Aucune documentation pertinente trouvée pour : requête vide."

        query_variants = _generate_query_variants(query)
        with _silence_native_stderr():
            collection = _get_chroma_collection()
            raw_results = [
                collection.query(
                    query_texts=[variant],
                    n_results=RAG_N_RESULTS_PER_QUERY,
                    include=["documents", "distances"],
                )
                for variant in query_variants
            ]

        candidates = _rerank_hybrid_candidates(query, raw_results)
        if not candidates:
            return (
                f"Aucune documentation pertinente trouvée pour : {query} "
                f"(meilleur résultat trop éloigné ou sans overlap lexical)."
            )

        best = candidates[0]
        lines = [
            (
                f"Documentation trouvée (Source: {best['id']}, pertinence: {best['distance']:.2f}, "
                f"score_hybride: {best['hybrid_score']:.2f}) :"
            ),
            best["document"],
            "",
            "Citations:",
        ]
        for cand in candidates:
            lines.append(
                f"- [{cand['id']}] distance={cand['distance']:.2f}, lexical={cand['lexical_score']:.2f} | "
                f"extrait: {_extract_snippet(cand['document'])}"
            )

        return "\n".join(lines)
    except Exception as e:
        return f"Aucune documentation trouvée. Erreur: {e}"
