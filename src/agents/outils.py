# CHATGPT
# On met les outils ici (chercher_ticket_similaire ... )

def verifier_statut_serveur(nom_serveur: str) -> str:
    """
    Vérifie l'état actuel d'un serveur ou d'un service informatique.
    Args:
        nom_serveur: Le nom du service (ex: 'VPN', 'Intranet', 'Mail').
    """
    print(f"\n[ACTION OUTIL] -> Vérification de la DB pour le service '{nom_serveur}'...")

    # Simulation d'une base de données d'incidents IT
    services_en_panne = ["VPN", "CISCO"]

    if nom_serveur.upper() in services_en_panne:
        return f"ALERTE : Le service {nom_serveur} est actuellement HORS LIGNE (Incident #4042 en cours)."

    return f"OK : Le service {nom_serveur} est EN LIGNE et fonctionne normalement."


def verifier_solde_conges(id_employe: str) -> str:
    """
    Vérifie le nombre de jours de congés restants pour un employé.
    Args:
        id_employe: Le matricule de l'employé (ex: 'EMP123').
    """
    print(f"\n[ACTION OUTIL] -> Interrogation du logiciel RH pour {id_employe}...")
    return f"L'employé {id_employe} possède 12 jours de congés payés restants."
# CHATGPT