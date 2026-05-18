"""Unit tests for src.agent.rag — ChromaDB initialisation from KB and docs."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.agent.rag import initialiser_documentation


def _mock_chroma_client():
    collection = MagicMock()
    client = MagicMock()
    client.get_or_create_collection.return_value = collection
    return client, collection


class TestInitialiserDocumentation:
    def test_upserts_kb_articles_found_in_kb_dir(self, tmp_path):
        client, collection = _mock_chroma_client()

        kb_article_dir = tmp_path / "articles" / "KB001"
        kb_article_dir.mkdir(parents=True)
        (kb_article_dir / "article.md").write_text("# KB001 content")

        with (
            patch("src.agent.rag.CHROMA_PATH", str(tmp_path / "vectordb")),
            patch("src.agent.rag.KB_DIR", str(tmp_path / "articles")),
            patch("src.agent.rag.DOC_MD_DIR", str(tmp_path / "docs_absent")),
            patch("src.agent.rag.chromadb.PersistentClient", return_value=client),
        ):
            initialiser_documentation()

        collection.upsert.assert_called_once()
        _, kwargs = collection.upsert.call_args
        assert "KB001" in kwargs["ids"]
        assert "# KB001 content" in kwargs["documents"]

    def test_upserts_technical_docs_from_doc_dir(self, tmp_path):
        client, collection = _mock_chroma_client()

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "guide.md").write_text("# Technical guide")

        with (
            patch("src.agent.rag.CHROMA_PATH", str(tmp_path / "vectordb")),
            patch("src.agent.rag.KB_DIR", str(tmp_path / "articles_empty")),
            patch("src.agent.rag.DOC_MD_DIR", str(docs_dir)),
            patch("src.agent.rag.chromadb.PersistentClient", return_value=client),
        ):
            initialiser_documentation()

        collection.upsert.assert_called_once()
        _, kwargs = collection.upsert.call_args
        assert "DOC_guide" in kwargs["ids"]

    def test_upserts_both_kb_articles_and_technical_docs(self, tmp_path):
        client, collection = _mock_chroma_client()

        kb_dir = tmp_path / "articles" / "KB002"
        kb_dir.mkdir(parents=True)
        (kb_dir / "article.md").write_text("kb content")

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "manual.md").write_text("doc content")

        with (
            patch("src.agent.rag.CHROMA_PATH", str(tmp_path / "vectordb")),
            patch("src.agent.rag.KB_DIR", str(tmp_path / "articles")),
            patch("src.agent.rag.DOC_MD_DIR", str(docs_dir)),
            patch("src.agent.rag.chromadb.PersistentClient", return_value=client),
        ):
            initialiser_documentation()

        collection.upsert.assert_called_once()
        _, kwargs = collection.upsert.call_args
        assert "KB002" in kwargs["ids"]
        assert "DOC_manual" in kwargs["ids"]

    def test_does_not_upsert_when_no_articles_found(self, tmp_path):
        client, collection = _mock_chroma_client()

        with (
            patch("src.agent.rag.CHROMA_PATH", str(tmp_path / "vectordb")),
            patch("src.agent.rag.KB_DIR", str(tmp_path / "articles_empty")),
            patch("src.agent.rag.DOC_MD_DIR", str(tmp_path / "docs_absent")),
            patch("src.agent.rag.chromadb.PersistentClient", return_value=client),
        ):
            initialiser_documentation()

        collection.upsert.assert_not_called()

    def test_ignores_non_markdown_files_in_doc_dir(self, tmp_path):
        client, collection = _mock_chroma_client()

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "image.png").write_bytes(b"\x89PNG")
        (docs_dir / "notes.txt").write_text("not markdown")
        (docs_dir / "valid.md").write_text("markdown content")

        with (
            patch("src.agent.rag.CHROMA_PATH", str(tmp_path / "vectordb")),
            patch("src.agent.rag.KB_DIR", str(tmp_path / "articles_empty")),
            patch("src.agent.rag.DOC_MD_DIR", str(docs_dir)),
            patch("src.agent.rag.chromadb.PersistentClient", return_value=client),
        ):
            initialiser_documentation()

        _, kwargs = collection.upsert.call_args
        assert kwargs["ids"] == ["DOC_valid"]
