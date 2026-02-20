import sys
import os
sys.path.append(os.getcwd()) 

from src.agents.maestro import lancer_agent

# CHATGPT
def test_ia_vpn():
    print("Test VPN en cours...")
    reponse = lancer_agent("Mon VPN Cisco est mort")
    # Si 'vpn' ou 'cisco' est dans la réponse, le test passe
    assert "vpn" in reponse.lower() or "cisco" in reponse.lower()
    print("✅ Test VPN OK")

def test_ia_outlook():
    print("Test Outlook en cours...")
    reponse = lancer_agent("Outlook ne s'ouvre pas")
    assert "outlook" in reponse.lower() or "mail" in reponse.lower()
    print("✅ Test Outlook OK")

# CHATGPT

if __name__ == "__main__":
    test_ia_vpn()

    test_ia_outlook()
