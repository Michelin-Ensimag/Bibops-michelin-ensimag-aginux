"""
tests/test_outils.py

Tests unitaires pour src/bibops/it_support/outils.py.
Toutes les dépendances externes (SQLite, fichier JSON, ChromaDB) sont mockées :
aucune base de données réelle n'est nécessaire pour exécuter cette suite.

TODO [T1-1a] verifier_statut_serveur – correspondance exacte
TODO [T1-1b] verifier_statut_serveur – correspondance partielle (ex : "Cisco VPN")
TODO [T1-1c] verifier_statut_serveur – serveur inconnu
TODO [T1-1d] verifier_statut_serveur – erreur SQL propagée en message
TODO [T1-2a] chercher_dans_kb – mot-clé connu → solution retournée
TODO [T1-2b] chercher_dans_kb – aucun mot-clé correspondant → recommandation ticket
TODO [T1-2c] chercher_dans_kb – fichier KB absent → message ERREUR
TODO [T1-3a] chercher_documentation_technique – distance < 1.2 → doc retournée
TODO [T1-3b] chercher_documentation_technique – distance >= 1.2 → rejetée
TODO [T1-3c] chercher_documentation_technique – exception ChromaDB → message d'erreur
"""
import json
from unittest.mock import MagicMock, mock_open, patch

from src.agent.tools import (
    chercher_dans_kb,
    chercher_documentation_technique,
    verifier_statut_serveur,
)

# ── Fixture : base de connaissances JSON factice ──────────────────────────────

FAKE_KB = {
    "knowledge_base": [
        {
            "mots_cles": ["vpn", "cisco"],
            "probleme": "VPN ne marche pas",
            "categorie": "Réseau",
            "priorite": "Haute",
            "solution": {
                "diagnostic": ["Vérifier la connexion réseau", "Relancer le service VPN"],
                "resolution": [
                    "Redémarrer le client Cisco AnyConnect",
                    "Relancer l'authentification MFA",
                ],
                "escalade": "Contacter le niveau 2 si le problème persiste.",
            },
        }
    ]
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sqlite_mock(mock_connect: MagicMock) -> tuple[MagicMock, MagicMock]:
    """Configure un mock sqlite3.connect() avec son curseur associé."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_connect.return_value.__enter__.return_value = mock_conn
    mock_connect.return_value.__exit__.return_value = False
    return mock_conn, mock_cursor


# ══════════════════════════════════════════════════════════════════════════════
# Tests : verifier_statut_serveur
# ══════════════════════════════════════════════════════════════════════════════

class TestVerifierStatutServeur:
    """TODO [T1-1] : Vérifie la logique de recherche SQLite (exact, partiel, inconnu, erreur)."""

    @patch("sqlite3.connect")
    def test_exact_match_returns_status(self, mock_connect):
        """TODO [T1-1a] : Correspondance exacte → statut formaté."""
        _, cursor = _sqlite_mock(mock_connect)
        cursor.fetchone.return_value = ("VPN", "HORS LIGNE (Incident 4042)")

        result = verifier_statut_serveur("VPN")

        assert "HORS LIGNE" in result
        assert "VPN" in result

    @patch("sqlite3.connect")
    def test_partial_match_returns_multiple_services(self, mock_connect):
        """TODO [T1-1b] : Pas de match exact → recherche mot par mot et retour multi-lignes."""
        _, cursor = _sqlite_mock(mock_connect)
        cursor.fetchone.return_value = None
        cursor.fetchall.return_value = [
            ("VPN", "HORS LIGNE (Incident 4042)"),
            ("CISCO", "EN LIGNE"),
        ]

        result = verifier_statut_serveur("Cisco VPN")

        assert "VPN" in result
        assert "CISCO" in result

    @patch("sqlite3.connect")
    def test_unknown_server_returns_not_found_message(self, mock_connect):
        """TODO [T1-1c] : Serveur totalement inconnu → message explicite."""
        _, cursor = _sqlite_mock(mock_connect)
        cursor.fetchone.return_value = None
        cursor.fetchall.return_value = []

        result = verifier_statut_serveur("MACHINE_INCONNUE")

        assert "inconnu" in result.lower() or "aucun" in result.lower()

    @patch("sqlite3.connect")
    def test_sql_error_returns_error_message_without_raising(self, mock_connect):
        """TODO [T1-1d] : Erreur SQL capturée → retourne un message, ne lève pas d'exception."""
        mock_connect.side_effect = Exception("DB locked")

        result = verifier_statut_serveur("VPN")

        assert "Erreur SQL" in result


# ══════════════════════════════════════════════════════════════════════════════
# Tests : chercher_dans_kb
# ══════════════════════════════════════════════════════════════════════════════

class TestChercherDansKB:
    """TODO [T1-2] : Vérifie le scoring par mots-clés sur le fichier JSON."""

    def test_matching_keyword_returns_solution(self):
        """TODO [T1-2a] : Mot-clé 'vpn' trouvé → solution formatée retournée."""
        with patch("builtins.open", mock_open(read_data=json.dumps(FAKE_KB))):
            result = chercher_dans_kb("vpn ne marche pas")

        assert "SOLUTION" in result
        assert "VPN" in result

    def test_no_matching_keyword_suggests_ticket(self):
        """TODO [T1-2b] : Aucun mot-clé connu → recommandation de créer un ticket."""
        with patch("builtins.open", mock_open(read_data=json.dumps(FAKE_KB))):
            result = chercher_dans_kb("problème de cafetière")

        assert "Aucune solution" in result or "ticket" in result.lower()

    def test_missing_kb_file_returns_error_message(self):
        """TODO [T1-2c] : Fichier JSON absent → retourne ERREUR sans lever d'exception."""
        with patch("builtins.open", side_effect=FileNotFoundError):
            result = chercher_dans_kb("vpn")

        assert "ERREUR" in result
        assert "introuvable" in result.lower()


# ══════════════════════════════════════════════════════════════════════════════
# Tests : chercher_documentation_technique
# ══════════════════════════════════════════════════════════════════════════════

class TestChercherDocumentationTechnique:
    """TODO [T1-3] : Vérifie le filtrage par seuil de distance cosine (ChromaDB mocké)."""

    @patch("src.agent.tools._chroma_client")
    def test_relevant_doc_returned_below_threshold(self, mock_chroma_client):
        """TODO [T1-3a] : Distance < 1.2 → document et identifiant retournés."""
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "documents": [["Procédure Bitlocker : récupération de clé de secours..."]],
            "distances": [[0.35]],
            "ids": [["KB_BITLOCKER"]],
        }
        mock_chroma_client.get_collection.return_value = mock_collection

        result = chercher_documentation_technique("bitlocker")

        assert "Bitlocker" in result
        assert "KB_BITLOCKER" in result

    @patch("src.agent.tools._chroma_client")
    def test_irrelevant_doc_rejected_above_threshold(self, mock_chroma_client):
        """TODO [T1-3b] : Distance >= 1.2 → résultat rejeté, message 'non pertinent'."""
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "documents": [["Document sans rapport"]],
            "distances": [[1.5]],
            "ids": [["KB_RANDOM"]],
        }
        mock_chroma_client.get_collection.return_value = mock_collection

        result = chercher_documentation_technique("sujet totalement inconnu")

        assert "Aucune documentation pertinente" in result

    @patch("src.agent.tools._chroma_client")
    def test_chroma_exception_returns_error_message(self, mock_chroma_client):
        """TODO [T1-3c] : Exception ChromaDB → retourne un message d'erreur, ne lève pas."""
        mock_chroma_client.get_collection.side_effect = Exception("ChromaDB indisponible")

        result = chercher_documentation_technique("bitlocker")

        assert "Aucune documentation trouvée" in result
        assert "Erreur" in result
