"""Run Copilot API smoke test."""

from src.test_copilot_api import tester_modele, MODELES, TICKET


if __name__ == "__main__":
    print("Benchmark Copilot API")
    for modele in MODELES:
        resultat = tester_modele(modele, TICKET)
        print(f"{modele}: {resultat['statut']} | {resultat['temps_s']}s | tokens={resultat['total_tokens']}")
