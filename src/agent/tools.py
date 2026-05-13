import json
import os
import re
import sqlite3
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
DB_PATH = os.path.join(BASE_DIR, 'data', 'databases', 'bibops.db')
CHROMA_PATH = os.path.join(BASE_DIR, 'data', 'databases', 'vectordb')


@dataclass(frozen=True)
class ToolPolicy:
    timeout_s: float
    max_retries: int
    min_arg_len: int
    max_arg_len: int


TOOL_POLICIES: dict[str, ToolPolicy] = {
    "verifier_statut_serveur":        ToolPolicy(timeout_s=3.0, max_retries=0, min_arg_len=2, max_arg_len=64),
    "chercher_documentation_technique": ToolPolicy(timeout_s=8.0, max_retries=1, min_arg_len=2, max_arg_len=120),
    "chercher_dans_kb":               ToolPolicy(timeout_s=5.0, max_retries=1, min_arg_len=2, max_arg_len=120),
}

RAG_DISTANCE_MAX = 1.2
RAG_N_RESULTS_PER_QUERY = 3
RAG_MAX_CITATIONS = 3
KB_MAX_RESULTS = 2
KB_MIN_SCORE = 4

KB_STOPWORDS = {
    "a", "ai", "au", "aux", "avec", "ce", "ces", "cet", "cette", "comment", "d", "de", "des", "du",
    "elle", "en", "est", "et", "faire", "il", "j", "je", "l", "la", "le", "les", "ma", "me", "mes",
    "mon", "ne", "nous", "ou", "pas", "peux", "plus", "pour", "qu", "que", "qui", "s", "se", "suis",
    "sur", "un", "une", "vous",
}

KB_GENERIC_PRODUCT_TERMS = {
    "outlook", "teams", "windows", "imprimante", "printer", "scanner", "vpn", "wifi", "sap", "proxy",
    "usb", "bluetooth", "micro", "cisco",
}


try:
    import chromadb
    _chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
except Exception:
    _chroma_client = None


def get_tool_policy(tool_name: str) -> ToolPolicy:
    return TOOL_POLICIES.get(tool_name, ToolPolicy(timeout_s=5.0, max_retries=0, min_arg_len=1, max_arg_len=120))


def get_tool_policies() -> dict[str, dict[str, Any]]:
    return {name: asdict(policy) for name, policy in TOOL_POLICIES.items()}


def normaliser_argument_outil(tool_name: str, argument: str) -> str:
    arg = (argument or "").strip()
    policy = get_tool_policy(tool_name)

    if len(arg) < policy.min_arg_len:
        raise ValueError(f"argument trop court (< {policy.min_arg_len})")
    if len(arg) > policy.max_arg_len:
        raise ValueError(f"argument trop long (> {policy.max_arg_len})")

    if tool_name == "verifier_statut_serveur":
        return " ".join(arg.replace("_", " ").split()).upper()

    return " ".join(arg.split())


# ── RAG helpers ───────────────────────────────────────────────────────────────

def _tokenize_query(text: str) -> list[str]:
    return [tok for tok in re.findall(r"[a-zA-Z0-9]+", text.lower()) if len(tok) >= 3]


def _normalize_search_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text or "")
    without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return without_accents.lower()


def _kb_tokens(text: str) -> set[str]:
    normalized = _normalize_search_text(text)
    return {
        tok
        for tok in re.findall(r"[a-z0-9]+", normalized)
        if len(tok) >= 3 and tok not in KB_STOPWORDS
    }


def _keyword_match_score(keyword: str, normalized_query: str, query_tokens: set[str]) -> int:
    keyword_tokens = _kb_tokens(keyword)
    if not keyword_tokens:
        return 0

    normalized_keyword = _normalize_search_text(keyword).strip()
    single_generic = len(keyword_tokens) == 1 and next(iter(keyword_tokens)) in KB_GENERIC_PRODUCT_TERMS

    if normalized_keyword and normalized_keyword in normalized_query:
        return 2 if single_generic else 10 + len(keyword_tokens)

    if keyword_tokens <= query_tokens:
        return 2 if single_generic else 7 + len(keyword_tokens)

    overlap = keyword_tokens & query_tokens
    if not overlap:
        return 0
    return len(overlap) if single_generic else 3 * len(overlap)


def _score_kb_entry(requete: str, entry: dict[str, Any]) -> int:
    normalized_query = _normalize_search_text(requete)
    query_tokens = _kb_tokens(requete)
    if not query_tokens:
        return 0

    keyword_score = sum(
        _keyword_match_score(str(keyword), normalized_query, query_tokens)
        for keyword in entry.get("mots_cles", [])
    )
    problem_overlap = len(query_tokens & _kb_tokens(str(entry.get("probleme", ""))))
    category_overlap = len(query_tokens & _kb_tokens(str(entry.get("categorie", ""))))

    if keyword_score == 0 and problem_overlap < 2:
        return 0

    return keyword_score + (2 * problem_overlap) + category_overlap


def _priority_rank(priority: str) -> int:
    normalized = _normalize_search_text(priority)
    if "haute" in normalized:
        return 3
    if "moyenne" in normalized:
        return 2
    if "basse" in normalized:
        return 1
    return 0


def _generate_query_variants(query: str) -> list[str]:
    normalized = " ".join(query.split())
    if not normalized:
        return []
    tokens = _tokenize_query(normalized)
    candidates = [
        normalized,
        " ".join(tokens) if len(tokens) > 1 else None,
        " ".join(tokens[:2]) if len(tokens) > 2 else None,
        tokens[0] if tokens else None,
    ]
    return list(dict.fromkeys(c for c in candidates if c))


def _lexical_overlap_score(query: str, document: str) -> float:
    q_tokens = set(_tokenize_query(query))
    if not q_tokens:
        return 0.0
    doc_tokens = set(_tokenize_query(document[:2500]))
    return len(q_tokens & doc_tokens) / len(q_tokens) if doc_tokens else 0.0


def _unwrap_chroma_list(value: list) -> list:
    """ChromaDB wraps results in a nested list when batching; flatten one level."""
    return value[0] if value and isinstance(value[0], list) else value


def _rerank_hybrid_candidates(query: str, raw_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}

    for result in raw_results:
        ids       = _unwrap_chroma_list(result.get("ids") or [])
        documents = _unwrap_chroma_list(result.get("documents") or [])
        distances = _unwrap_chroma_list(result.get("distances") or [])

        for idx, doc_id in enumerate(ids):
            doc_text = documents[idx] if idx < len(documents) else ""
            distance = distances[idx] if idx < len(distances) else None
            if distance is None:
                continue

            lexical = _lexical_overlap_score(query, doc_text)
            vector_score = 1.0 / (1.0 + float(distance))
            hybrid_score = round((0.75 * vector_score) + (0.25 * lexical), 4)

            candidate = {
                "id": doc_id,
                "document": doc_text,
                "distance": float(distance),
                "lexical_score": round(lexical, 4),
                "hybrid_score": hybrid_score,
            }
            current = by_id.get(doc_id)
            if current is None or hybrid_score > current["hybrid_score"]:
                by_id[doc_id] = candidate

    ranked = sorted(by_id.values(), key=lambda c: c["hybrid_score"], reverse=True)
    return [
        c for c in ranked
        if c["distance"] < RAG_DISTANCE_MAX or c["lexical_score"] >= 0.25
    ][:RAG_MAX_CITATIONS]


def _extract_snippet(document: str, max_chars: int = 220) -> str:
    one_line = " ".join(document.replace("\n", " ").split())
    return one_line if len(one_line) <= max_chars else one_line[: max_chars - 3] + "..."


# ── Tools ─────────────────────────────────────────────────────────────────────

def verifier_statut_serveur(nom_serveur: str) -> str:
    """Vérifie l'état d'un serveur dans la base de données SQLite."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT nom, statut FROM serveurs_it WHERE nom = ?", (nom_serveur.upper(),))
            row = cursor.fetchone()
            if row:
                nom, statut = row
                statut_upper = statut.upper()
                if "HORS LIGNE" in statut_upper:
                    return (
                        f"Statut : Le service {nom} est {statut}.\n"
                        "Diagnostic : incident côté service probable, les manipulations locales ne suffisent probablement pas.\n"
                        "Actions : informer l'utilisateur de l'incident, proposer de réessayer plus tard ou d'utiliser le service de secours si disponible, "
                        "puis escalader à l'équipe infrastructure avec l'ID d'incident."
                    )
                return (
                    f"Statut : Le service {nom} est {statut}.\n"
                    "Diagnostic : aucune panne globale détectée sur ce service.\n"
                    "Actions : poursuivre le diagnostic local (poste, réseau, cache, droits, client applicatif), collecter le message d'erreur exact, "
                    "puis consulter la KB ou escalader si le problème persiste."
                )

            mots = nom_serveur.upper().replace("_", " ").split()
            placeholders = " OR ".join("nom = ?" for _ in mots)
            cursor.execute(f"SELECT nom, statut FROM serveurs_it WHERE {placeholders}", mots)
            rows = cursor.fetchall()
            if rows:
                lignes = "\n".join(f"- {nom} : {statut}" for nom, statut in rows)
                return (
                    f"Services correspondants :\n{lignes}\n"
                    "Actions : sélectionner le service le plus proche du ticket, puis compléter avec un diagnostic KB si le service est en ligne."
                )
            return f"Service inconnu : Aucun serveur nommé {nom_serveur}."
    except Exception as e:
        return f"Erreur SQL : {e}"


def chercher_dans_kb(requete: str) -> str:
    """Utilise CET outil pour chercher des solutions basiques (mots clés) dans la base de connaissances classique (JSON)."""
    print(f"\n[ACTION OUTIL] -> Recherche dans la KB pour : '{requete}'...")
    kb_path = os.path.join(BASE_DIR, 'data', 'kb', 'knowledge_base.json')
    try:
        with open(kb_path, encoding="utf-8") as f:
            kb = json.load(f)["knowledge_base"]
    except FileNotFoundError:
        return "ERREUR : Knowledge Base introuvable."
    except json.JSONDecodeError:
        return "ERREUR : Knowledge Base corrompue."

    scored = []
    for entry in kb:
        score = _score_kb_entry(requete, entry)
        if score >= KB_MIN_SCORE:
            scored.append((score, entry))

    scored.sort(key=lambda x: (x[0], _priority_rank(str(x[1].get("priorite", "")))), reverse=True)

    if not scored:
        return f"Aucune solution trouvée pour '{requete}'. Recommandation : créer un ticket support."

    best_score = scored[0][0]
    top = [(score, entry) for score, entry in scored if score == best_score][:KB_MAX_RESULTS]

    reponse = f"{len(top)} solution(s) trouvée(s) :\n\n"
    for idx, (score, entry) in enumerate(top, 1):
        reponse += (
            f"--- SOLUTION {idx} ---\n"
            f"ID : {entry.get('id', f'KB-{idx}')}\n"
            f"Score KB : {score}\n"
            f"Problème : {entry['probleme']}\n"
            f"Catégorie : {entry['categorie']}\n"
            f"Priorité : {entry['priorite']}\n\n"
        )
        if entry["solution"].get("diagnostic"):
            reponse += "DIAGNOSTIC :\n" + "".join(f"  - {s}\n" for s in entry["solution"]["diagnostic"]) + "\n"
        reponse += "RÉSOLUTION :\n" + "".join(f"  {i}. {s}\n" for i, s in enumerate(entry["solution"]["resolution"], 1)) + "\n"
        if entry["solution"].get("escalade"):
            reponse += f"ESCALADE : {entry['solution']['escalade']}\n\n"

    return reponse


def chercher_documentation_technique(mot_cle: str) -> str:
    """Utilise CET outil pour chercher des procédures techniques longues ou des tutoriels détaillés (Bitlocker, VPN) dans les articles officiels Michelin (Vector DB)."""
    try:
        query = " ".join((mot_cle or "").split())
        if not query:
            return "Aucune documentation pertinente trouvée pour : requête vide."
        if _chroma_client is None:
            return "Aucune documentation trouvée. Erreur: ChromaDB indisponible"

        collection = _chroma_client.get_collection(name="doc_michelin")
        raw_results = [
            collection.query(query_texts=[v], n_results=RAG_N_RESULTS_PER_QUERY, include=["documents", "distances"])
            for v in _generate_query_variants(query)
        ]

        candidates = _rerank_hybrid_candidates(query, raw_results)
        if not candidates:
            return f"Aucune documentation pertinente trouvée pour : {query} (meilleur résultat trop éloigné ou sans overlap lexical)."

        best = candidates[0]
        lines = [
            f"Documentation trouvée (Source: {best['id']}, pertinence: {best['distance']:.2f}, score_hybride: {best['hybrid_score']:.2f}) :",
            best["document"],
            "",
            "Citations:",
        ] + [
            f"- [{c['id']}] distance={c['distance']:.2f}, lexical={c['lexical_score']:.2f} | extrait: {_extract_snippet(c['document'])}"
            for c in candidates
        ]
        return "\n".join(lines)
    except Exception as e:
        return f"Aucune documentation trouvée. Erreur: {e}"
