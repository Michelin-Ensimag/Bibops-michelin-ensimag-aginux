# # CHATGPT
# import sys
# import os
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
#
# from src.agents.maestro import lancer_agent
# from src.agents.outils import verifier_statut_serveur
#
# contexte_it = "Tu es l'agent IA de support informatique Michelin. Utilise tes outils."
#
# def test_ia_vpn():
#     print("Test VPN en cours...")
#     reponse = lancer_agent("Mon VPN Cisco est mort",contexte_it,outils_disponibles=[verifier_statut_serveur])
#     # Si 'vpn' ou 'cisco' est dans la réponse, le test passe
#     assert "vpn" in reponse.lower() or "cisco" in reponse.lower()
#     print("Test VPN OK")
#
# def test_ia_outlook():
#     print("Test Outlook en cours...")
#     reponse = lancer_agent("Outlook ne s'ouvre pas",contexte_it,outils_disponibles=[verifier_statut_serveur])
#     assert "outlook" in reponse.lower() or "mail" in reponse.lower()
#     print("Test Outlook OK")
#
# if __name__ == "__main__":
#     test_ia_vpn()
#     test_ia_outlook()
# # CHATGPT