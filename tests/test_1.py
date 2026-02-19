from src.agents.outils import verifier_statut_serveur

def test_vpn_en_panne():
    assert "HORS LIGNE" in verifier_statut_serveur("VPN")

def test_imprimante_ok():
    assert "EN LIGNE" in verifier_statut_serveur("Imprimante")