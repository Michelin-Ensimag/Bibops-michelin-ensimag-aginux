"""Tests for agent infrastructure: database.py, mcp_server.py, rag.py."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# database.py
# ---------------------------------------------------------------------------

class TestInitialiserBaseDeDonnees:
    def test_creates_serveurs_it_table(self, tmp_path, monkeypatch):
        db_file = tmp_path / "test_bibops.db"
        monkeypatch.setenv("DUMMY", "1")  # no-op, just ensuring monkeypatch is available

        with patch("src.agent.database.DB_PATH", str(db_file)):
            from src.agent.database import initialiser_base_de_donnees
            initialiser_base_de_donnees()

        assert db_file.exists()
        with sqlite3.connect(str(db_file)) as conn:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "serveurs_it" in tables

    def test_idempotent_create_if_not_exists(self, tmp_path):
        db_file = tmp_path / "idempotent.db"
        with patch("src.agent.database.DB_PATH", str(db_file)):
            from src.agent.database import initialiser_base_de_donnees
            initialiser_base_de_donnees()
            initialiser_base_de_donnees()  # second call must not raise

        assert db_file.exists()


# ---------------------------------------------------------------------------
# mcp_server.py — tool registration
# ---------------------------------------------------------------------------

class TestMCPServer:
    def test_mcp_instance_exists(self):
        from src.agent.mcp_server import mcp
        assert mcp is not None

    def test_mcp_has_three_tools(self):
        import asyncio
        from src.agent.mcp_server import mcp
        tools = asyncio.run(mcp.list_tools())
        assert len(tools) == 3

    def test_tool_names_registered(self):
        import asyncio
        from src.agent.mcp_server import mcp
        tools = asyncio.run(mcp.list_tools())
        names = {t.name for t in tools}
        assert "mcp_verifier_statut_serveur" in names
        assert "mcp_chercher_documentation_technique" in names
        assert "mcp_chercher_dans_kb" in names

    def test_mcp_verifier_statut_serveur_delegates_to_tool(self):
        """The MCP tool function body is covered via call_tool."""
        import asyncio
        from unittest.mock import patch
        from src.agent.mcp_server import mcp

        with patch("src.agent.mcp_server.verifier_statut_serveur", return_value="OK"):
            result = asyncio.run(mcp.call_tool("mcp_verifier_statut_serveur", {"nom_serveur": "VPN"}))
        assert result is not None

    def test_mcp_chercher_dans_kb_delegates_to_tool(self):
        import asyncio
        from unittest.mock import patch
        from src.agent.mcp_server import mcp

        with patch("src.agent.mcp_server.chercher_dans_kb", return_value="KB result"):
            result = asyncio.run(mcp.call_tool("mcp_chercher_dans_kb", {"requete": "VPN"}))
        assert result is not None


# ---------------------------------------------------------------------------
# rag.py — import and basic init (no real ChromaDB)
# ---------------------------------------------------------------------------

class TestRagModule:
    def test_module_imports_without_error(self):
        """Just import the module — exercises module-level constants."""
        import src.agent.rag  # noqa: F401

    def test_chroma_path_constant_exists(self):
        from src.agent.rag import CHROMA_PATH
        assert isinstance(CHROMA_PATH, str)
        assert len(CHROMA_PATH) > 0

    def test_initialiser_documentation_with_mock_chromadb(self, tmp_path):
        """initialiser_documentation with mocked chromadb and empty directories."""
        fake_collection = MagicMock()
        fake_client = MagicMock()
        fake_client.get_or_create_collection.return_value = fake_collection

        with patch("src.agent.rag.chromadb.PersistentClient", return_value=fake_client), \
             patch("src.agent.rag.CHROMA_PATH", str(tmp_path / "vectordb")), \
             patch("src.agent.rag.KB_DIR", str(tmp_path / "kb_articles")), \
             patch("src.agent.rag.DOC_MD_DIR", str(tmp_path / "docs")):
            from src.agent.rag import initialiser_documentation
            initialiser_documentation()

        fake_client.get_or_create_collection.assert_called_once_with(name="doc_michelin")
