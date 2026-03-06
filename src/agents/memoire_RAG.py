import chromadb
import os

# Chemins d'accès
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
CHROMA_PATH = os.path.join(BASE_DIR, 'data', 'vectordb')
KB_DIR = os.path.join(BASE_DIR, 'data', 'IN - EUX Service Line')


def initialiser_documentation():
    print("📚 Initialisation de la Vector DB avec la Vraie Knowledge Base Michelin...")

    client = chromadb.PersistentClient(path=CHROMA_PATH)

    # On supprime l'ancienne collection si elle existe pour repartir au propre
    try:
        client.delete_collection(name="doc_michelin")
    except Exception:
        pass

    collection = client.create_collection(name="doc_michelin")

    documents = []
    ids = []

    # Parcours magique de tous les dossiers de la Knowledge Base
    for root, dirs, files in os.walk(KB_DIR):
        for file in files:
            if file == "article.md":
                file_path = os.path.join(root, file)
                # Le nom du dossier parent devient l'ID (ex: KB0010356)
                kb_id = os.path.basename(root)

                # On lit le contenu du fichier Markdown
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    documents.append(content)
                    ids.append(kb_id)
                    print(f"   📄 Ajout de l'article : {kb_id}")

    # Injection dans la base de données
    if documents:
        collection.add(documents=documents, ids=ids)
        print(f"\n✅ {len(documents)} articles vectorisés avec succès dans : {CHROMA_PATH}")
    else:
        print("\n⚠️ Aucun article trouvé. Vérifie le chemin du dossier KB.")

if __name__ == "__main__":
    initialiser_documentation()