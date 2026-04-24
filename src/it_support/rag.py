import chromadb
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
CHROMA_PATH = os.path.join(BASE_DIR, 'data', 'databases', 'vectordb')
KB_DIR = os.path.join(BASE_DIR, 'data', 'knowledge_base', 'articles')
DOC_MD_DIR = os.path.join(BASE_DIR, 'data', 'knowledge_base', 'doc_md')


def initialiser_documentation():
    print("Initialisation de la Vector DB avec la Knowledge Base Michelin...")

    os.makedirs(CHROMA_PATH, exist_ok=True)
    client = chromadb.PersistentClient(path=CHROMA_PATH) # persistant pour dire les donnes sauvg sur disque

    # # On supprime l'ancienne collection si elle existe pour repartir au propre
    # try:
    #     client.delete_collection(name="doc_michelin")
    # except Exception: # c est dangeureux cette ligne car exeption capture tous les prob , du coup s il y une autre exept que celle de colect inxsitant , elle serait silencieusement ignore
    #     pass

    try:
        collection = client.get_or_create_collection(name="doc_michelin")
    except AttributeError:
        try:
            collection = client.get_collection(name="doc_michelin")
        except Exception:
            collection = client.create_collection(name="doc_michelin")

    documents = []
    ids = []

    # 1. Parcours des articles KB (IN - EUX Service Line)
    for root, dirs, files in os.walk(KB_DIR):
        for file in files:
            if file == "article.md":
                file_path = os.path.join(root, file)
                kb_id = os.path.basename(root)

                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    documents.append(content)
                    ids.append(kb_id)
                    print(f"[Ajout de l'article michelin] : {kb_id}")

    # 2. Parcours des documentations techniques (doc_md/)
    if os.path.isdir(DOC_MD_DIR):
        for file in os.listdir(DOC_MD_DIR):
            if file.endswith('.md'):
                file_path = os.path.join(DOC_MD_DIR, file)
                doc_id = f"DOC_{os.path.splitext(file)[0]}"

                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    documents.append(content)
                    ids.append(doc_id)
                    print(f"[Ajout de la doc technique] : {doc_id}")

    # Injection dans la base de données
    if documents:
        # Déduplique les IDs pour permettre des relances idempotentes.
        docs_by_id = {}
        for doc_id, doc_content in zip(ids, documents):
            docs_by_id[doc_id] = doc_content

        dedup_ids = list(docs_by_id.keys())
        dedup_docs = [docs_by_id[i] for i in dedup_ids]

        if hasattr(collection, "upsert"):
            collection.upsert(documents=dedup_docs, ids=dedup_ids)
        else:
            collection.add(documents=dedup_docs, ids=dedup_ids)
        print(f"\n[Vector DB] : {len(dedup_docs)} articles synchronisés avec succès dans : {CHROMA_PATH}")
    else:
        print("\n[Vector DB] : Aucun article trouvé.")

if __name__ == "__main__":
    initialiser_documentation()
