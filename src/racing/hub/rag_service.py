"""
Racing Hub — RAG Service
Fournit un accès vectoriel asynchrone à la documentation Michelin Motorsport.

Collection ChromaDB : "racing_kb"
Embeddings         : OllamaEmbeddings (même modèle qu'à l'ingestion)

Utilisation :
    rag = RacingRAG()
    context = await rag.ask_question("Quels pneus pour piste humide ?")
    # → str avec les 3 meilleurs passages, prêt à alimenter un prompt LLM
"""

from __future__ import annotations

import asyncio
import os
from typing import ClassVar

import chromadb
from langchain_ollama import OllamaEmbeddings

# ---------------------------------------------------------------------------
# Configuration (doit correspondre à ingest_racing.py)
# ---------------------------------------------------------------------------

_BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))

CHROMA_PATH     = os.path.join(_BASE, "data", "databases", "vectordb")
COLLECTION_NAME = "racing_kb"
EMBED_MODEL     = "nomic-embed-text"
TOP_K           = 3


# ---------------------------------------------------------------------------
# Service RAG
# ---------------------------------------------------------------------------

class RacingRAG:
    """
    Accès asynchrone à la base vectorielle "racing_kb".

    Initialisation paresseuse : la connexion ChromaDB et le modèle d'embedding
    ne sont chargés qu'au premier appel, pas au démarrage du serveur.
    """

    # Singletons partagés entre les requêtes FastAPI
    _chroma_client: ClassVar[chromadb.PersistentClient | None] = None
    _embeddings:    ClassVar[OllamaEmbeddings | None]          = None

    def _get_collection(self) -> chromadb.Collection:
        if RacingRAG._chroma_client is None:
            RacingRAG._chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
        return RacingRAG._chroma_client.get_collection(name=COLLECTION_NAME)

    def _get_embeddings(self) -> OllamaEmbeddings:
        if RacingRAG._embeddings is None:
            RacingRAG._embeddings = OllamaEmbeddings(model=EMBED_MODEL)
        return RacingRAG._embeddings

    def _search_sync(self, question: str) -> str:
        """Recherche synchrone (appelée via asyncio.to_thread)."""
        collection = self._get_collection()
        embeddings = self._get_embeddings()

        query_vector = embeddings.embed_query(question)
        results = collection.query(
            query_embeddings=[query_vector],
            n_results=TOP_K,
            include=["documents", "metadatas", "distances"],
        )

        docs      = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]

        if not docs:
            return (
                f'[RAG vide] Aucun résultat dans la collection "{COLLECTION_NAME}".\n'
                "Lancez d'abord : python -m src.racing.hub.ingest_racing"
            )

        sections = []
        for i, (text, meta) in enumerate(zip(docs, metadatas), 1):
            source = meta.get("source", "inconnu") if meta else "inconnu"
            page   = meta.get("page", "") if meta else ""
            ref    = os.path.basename(str(source)) + (f" p.{page}" if page != "" else "")
            sections.append(f"--- Source {i} [{ref}] ---\n{text.strip()}")

        return "\n\n".join(sections)

    async def ask_question(self, question: str) -> str:
        """
        Recherche les passages les plus pertinents pour `question`.

        Returns:
            Contexte brut (TOP_K chunks concaténés) prêt à être transmis à
            une écurie pour alimenter son propre LLM.
        """
        try:
            return await asyncio.to_thread(self._search_sync, question)
        except Exception as exc:
            return (
                "[RAG indisponible] Impossible d'interroger la base vectorielle.\n"
                f"Cause : {exc}\n"
                "Vérifiez qu'Ollama tourne (ollama serve) et que l'ingestion a été faite."
            )
