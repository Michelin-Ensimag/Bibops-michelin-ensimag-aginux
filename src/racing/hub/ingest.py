"""
Racing Hub — Ingestion RAG
Vectorise les documents Michelin Motorsport placés dans :
    data/kb/racing_docs/

Formats supportés : .pdf  .md  .txt

Stockage : ChromaDB natif (cohérent avec l'existant) dans data/databases/vectordb/
Collection : "racing_kb"  (isolée de la collection IT "doc_michelin")

Embeddings : OllamaEmbeddings → modèle configurable via EMBED_MODEL
             Assurez-vous que le modèle est disponible localement :
               ollama pull nomic-embed-text

Usage :
    python -m src.racing.hub.ingest
    python -m src.racing.hub.ingest --reset   # repart de zéro
"""

from __future__ import annotations

import os
import sys

import chromadb
from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader, TextLoader
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

# ---------------------------------------------------------------------------
# Chemins & configuration
# ---------------------------------------------------------------------------

_BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))

RACING_DOCS_DIR = os.path.join(_BASE, "data", "kb", "racing_docs")
CHROMA_PATH     = os.path.join(_BASE, "data", "databases", "vectordb")
COLLECTION_NAME = "racing_kb"
EMBED_MODEL     = "nomic-embed-text"   # ollama pull nomic-embed-text

# ---------------------------------------------------------------------------
# Splitter partagé
# ---------------------------------------------------------------------------

_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    length_function=len,
)

# ---------------------------------------------------------------------------
# Chargement des documents
# ---------------------------------------------------------------------------

def _load_all_documents(docs_dir: str) -> list:
    """Charge .pdf, .md et .txt depuis `docs_dir` (récursif)."""
    all_docs = []

    loaders = [
        DirectoryLoader(
            docs_dir,
            glob="**/*.pdf",
            loader_cls=PyPDFLoader,
            show_progress=True,
            use_multithreading=False,
            silent_errors=True,
        ),
        DirectoryLoader(
            docs_dir,
            glob="**/*.md",
            loader_cls=TextLoader,
            loader_kwargs={"encoding": "utf-8"},
            show_progress=True,
            silent_errors=True,
        ),
        DirectoryLoader(
            docs_dir,
            glob="**/*.txt",
            loader_cls=TextLoader,
            loader_kwargs={"encoding": "utf-8"},
            show_progress=True,
            silent_errors=True,
        ),
    ]

    for loader in loaders:
        try:
            docs = loader.load()
            all_docs.extend(docs)
        except Exception as exc:
            print(f"  [WARN] Chargeur ignoré : {exc}")

    return all_docs

# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

def ingest(reset: bool = False) -> None:
    """
    Lance le pipeline d'ingestion complet.

    Args:
        reset: Si True, supprime et recrée la collection "racing_kb"
               avant d'injecter (full-refresh).
    """
    print(f"\n{'═' * 60}")
    print("  BibOps Racing Hub — Ingestion RAG (racing_kb)")
    print(f"{'═' * 60}\n")

    # Vérification du dossier source
    if not os.path.isdir(RACING_DOCS_DIR):
        os.makedirs(RACING_DOCS_DIR, exist_ok=True)
        print(f"[INFO] Dossier créé : {RACING_DOCS_DIR}")
        print("[INFO] Placez vos .pdf/.md/.txt dans ce dossier puis relancez.")
        sys.exit(0)

    # 1 — Chargement
    print(f"[1/4] Chargement depuis :\n      {RACING_DOCS_DIR}")
    raw_docs = _load_all_documents(RACING_DOCS_DIR)

    if not raw_docs:
        print("\n[WARN] Aucun document trouvé. Ajoutez des fichiers dans racing_docs/ puis relancez.")
        sys.exit(0)

    print(f"       → {len(raw_docs)} document(s) chargé(s).")

    # 2 — Découpage
    print("\n[2/4] Découpage (size=500, overlap=50)...")
    chunks = _SPLITTER.split_documents(raw_docs)
    print(f"       → {len(chunks)} chunks produits.")

    # 3 — Embeddings
    print(f"\n[3/4] Calcul des embeddings via Ollama ({EMBED_MODEL})...")
    embeddings = OllamaEmbeddings(model=EMBED_MODEL)
    texts     = [c.page_content for c in chunks]
    metadatas = [c.metadata for c in chunks]
    vectors   = embeddings.embed_documents(texts)
    print(f"       → {len(vectors)} vecteurs calculés (dim={len(vectors[0])}).")

    # 4 — Stockage ChromaDB
    print(f"\n[4/4] Injection dans ChromaDB — collection \"{COLLECTION_NAME}\"...")
    os.makedirs(CHROMA_PATH, exist_ok=True)
    client = chromadb.PersistentClient(path=CHROMA_PATH)

    if reset:
        try:
            client.delete_collection(COLLECTION_NAME)
            print(f"       [RESET] Collection \"{COLLECTION_NAME}\" supprimée.")
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    # Inject par batches de 100 pour éviter les timeouts
    batch_size = 100
    for start in range(0, len(chunks), batch_size):
        end   = min(start + batch_size, len(chunks))
        ids   = [f"chunk_{start + i}" for i in range(end - start)]
        collection.add(
            documents=texts[start:end],
            embeddings=vectors[start:end],
            metadatas=metadatas[start:end],
            ids=ids,
        )
        print(f"       Batch {start}–{end} injecté.")

    print(f"\n✅ Ingestion terminée : {len(chunks)} chunks → \"{COLLECTION_NAME}\"")
    print(f"   Chemin : {CHROMA_PATH}\n")


# ---------------------------------------------------------------------------
# Entrée directe
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    reset_flag = "--reset" in sys.argv
    ingest(reset=reset_flag)
