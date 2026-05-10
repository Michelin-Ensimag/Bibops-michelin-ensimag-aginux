"""
tests/test_memoire.py

Tests unitaires pour src/bibops/it_support/memoire_courte.py.
Valide la logique de fenêtre glissante de MemoCourTerme sans aucune dépendance externe.

TODO [T1-2a] Initialisation – historique vide, max_messages correct
TODO [T1-2b] add_message    – messages ajoutés dans le bon ordre
TODO [T1-2c] Sliding window – max_messages=2, ajout de 3 → taille reste 2
TODO [T1-2d] Sliding window – les messages les PLUS RÉCENTS sont conservés
"""

from src.agent.memory import MemoCourTerme


class TestMemoCourTerme:

    # ── Initialisation ────────────────────────────────────────────────────────

    def test_initial_history_is_empty(self):
        """TODO [T1-2a] : La mémoire démarre avec un historique vide."""
        memo = MemoCourTerme(max_messages=5)
        assert memo.get_messages() == []

    def test_initial_max_messages_is_stored(self):
        """TODO [T1-2a] : max_messages est correctement conservé."""
        memo = MemoCourTerme(max_messages=7)
        assert memo.max_messages == 7

    # ── Ajout de messages ─────────────────────────────────────────────────────

    def test_add_message_appends_correct_dict(self):
        """TODO [T1-2b] : add_message crée un dict {role, content} dans l'historique."""
        memo = MemoCourTerme()
        memo.add_message("user", "Bonjour")

        messages = memo.get_messages()
        assert len(messages) == 1
        assert messages[0] == {"role": "user", "content": "Bonjour"}

    def test_add_multiple_messages_preserves_order(self):
        """TODO [T1-2b] : L'ordre d'insertion est respecté."""
        memo = MemoCourTerme(max_messages=10)
        memo.add_message("user", "Message 1")
        memo.add_message("assistant", "Message 2")
        memo.add_message("user", "Message 3")

        messages = memo.get_messages()
        assert messages[0]["content"] == "Message 1"
        assert messages[1]["content"] == "Message 2"
        assert messages[2]["content"] == "Message 3"

    # ── Fenêtre glissante ─────────────────────────────────────────────────────

    def test_sliding_window_size_does_not_exceed_max(self):
        """TODO [T1-2c] : max_messages=2, ajout de 3 messages → taille reste 2."""
        memo = MemoCourTerme(max_messages=2)
        memo.add_message("user", "A")
        memo.add_message("assistant", "B")
        memo.add_message("user", "C")  # doit évincer "A"

        assert len(memo.get_messages()) == 2

    def test_sliding_window_keeps_most_recent_messages(self):
        """TODO [T1-2d] : Les N messages les plus récents sont conservés, pas les anciens."""
        memo = MemoCourTerme(max_messages=2)
        memo.add_message("user", "ancien")
        memo.add_message("assistant", "récent-1")
        memo.add_message("user", "récent-2")

        messages = memo.get_messages()
        contents = [m["content"] for m in messages]

        assert "ancien" not in contents
        assert "récent-1" in contents
        assert "récent-2" in contents

    def test_sliding_window_with_exact_max_messages_does_not_trim(self):
        """TODO [T1-2d] : Exactement max_messages messages → aucun éviction."""
        memo = MemoCourTerme(max_messages=3)
        memo.add_message("user", "A")
        memo.add_message("assistant", "B")
        memo.add_message("user", "C")

        assert len(memo.get_messages()) == 3
