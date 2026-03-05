import chromadb
import os

# On recule de deux dossiers pour atteindre data/
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
CHROMA_PATH = os.path.join(BASE_DIR, 'data', 'vectordb')

def initialiser_documentation():
    print("Initialisation de la Vector DB Michelin (ChromaDB)...")
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_or_create_collection(name="doc_michelin")

    documents = [
        "Pour réinitialiser un mot de passe Outlook, l'utilisateur doit se rendre sur my.michelin.com/reset.",
        "Le serveur VPN Cisco de secours se trouve à l'adresse vpn2.michelin.fr et nécessite le port 443.",
        "En cas d'erreur 404 sur l'imprimante HP, il faut redémarrer le spooler d'impression via la commande net stop spooler."
    ]
    ids = ["doc_outlook", "doc_vpn", "doc_imprimante"]

    collection.add(documents=documents, ids=ids)
    print(f"Documentation vectorisée dans : {CHROMA_PATH}")

if __name__ == "__main__":
    initialiser_documentation()