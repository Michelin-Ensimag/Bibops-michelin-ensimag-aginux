import os

import chromadb

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
CHROMA_PATH = os.path.join(BASE_DIR, 'data', 'databases', 'vectordb')
KB_DIR = os.path.join(BASE_DIR, 'data', 'kb', 'articles')
DOC_MD_DIR = os.path.join(BASE_DIR, 'data', 'kb', 'docs')


def initialiser_documentation():
    print("Initialisation de la Vector DB avec la Knowledge Base Michelin...")
    os.makedirs(CHROMA_PATH, exist_ok=True)

    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_or_create_collection(name="doc_michelin")

    docs_by_id: dict[str, str] = {}

    for root, _, files in os.walk(KB_DIR):
        for file in files:
            if file == "article.md":
                kb_id = os.path.basename(root)
                with open(os.path.join(root, file), encoding="utf-8") as f:
                    docs_by_id[kb_id] = f.read()
                print(f"[Ajout de l'article michelin] : {kb_id}")

    if os.path.isdir(DOC_MD_DIR):
        for file in os.listdir(DOC_MD_DIR):
            if file.endswith(".md"):
                doc_id = f"DOC_{os.path.splitext(file)[0]}"
                with open(os.path.join(DOC_MD_DIR, file), encoding="utf-8") as f:
                    docs_by_id[doc_id] = f.read()
                print(f"[Ajout de la doc technique] : {doc_id}")

    if docs_by_id:
        ids = list(docs_by_id.keys())
        collection.upsert(documents=[docs_by_id[i] for i in ids], ids=ids)
        print(f"\n[Vector DB] : {len(ids)} articles synchronisés avec succès dans : {CHROMA_PATH}")
    else:
        print("\n[Vector DB] : Aucun article trouvé.")


if __name__ == "__main__":
    initialiser_documentation()
