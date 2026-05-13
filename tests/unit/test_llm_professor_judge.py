"""Tests for LLMProfessor using a mocked LLMJudge."""
from __future__ import annotations

import sqlite3
from unittest.mock import patch

from src.bibops.evaluation.judges.llm_judge import JudgeVerdict
from src.bibops.evaluation.judges.llm_professor import LLMProfessor


def _make_professor(db_path: str, verdict: JudgeVerdict) -> LLMProfessor:
    """Build a LLMProfessor whose internal LLMJudge is replaced with a mock."""
    import json

    from tests._fakes.fake_openai import FakeOpenAI, make_response

    content = json.dumps({"score": verdict.score, "justification": verdict.justification})
    fake_client = FakeOpenAI(make_response(content))

    prof = LLMProfessor.__new__(LLMProfessor)
    prof.db_path = db_path

    from src.bibops.evaluation.judges.llm_judge import LLMJudge
    prof._judge = LLMJudge(client=fake_client, model="gpt-4o-mock")
    return prof


def _init_db(db_path: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY,
                texte_utilisateur TEXT
            );
            CREATE TABLE IF NOT EXISTS evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER,
                modele TEXT,
                reponse_ia TEXT,
                temps_reponse_s REAL,
                note_juge INTEGER,
                justification_juge TEXT
            );
        """)
        conn.execute("INSERT INTO tickets VALUES (1, 'VPN broken')")
        conn.commit()


class TestEvaluerReponse:
    def test_returns_note_and_justification(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db)
        verdict = JudgeVerdict(score=8.0, justification="Good answer")
        prof = _make_professor(db, verdict)
        result = prof.evaluer_reponse(
            ticket_id=1,
            ticket_texte="VPN broken",
            reponse_agent="Restart AnyConnect",
            modele_agent="phi3",
            temps_reponse=1.0,
        )
        assert result is not None
        assert result["note"] == 8
        assert result["justification"] == "Good answer"

    def test_persists_to_db(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db)
        verdict = JudgeVerdict(score=7.0, justification="ok")
        prof = _make_professor(db, verdict)
        prof.evaluer_reponse(
            ticket_id=1,
            ticket_texte="problem",
            reponse_agent="answer",
            modele_agent="m",
            temps_reponse=0.5,
        )
        with sqlite3.connect(db) as conn:
            row = conn.execute("SELECT note_juge FROM evaluations WHERE ticket_id=1").fetchone()
        assert row is not None
        assert row[0] == 7

    def test_returns_none_on_judge_error(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db)
        # JudgeVerdict with error justification
        verdict = JudgeVerdict(score=0.0, justification="judge_error: connection failed")
        prof = _make_professor(db, verdict)
        result = prof.evaluer_reponse(
            ticket_id=1,
            ticket_texte="test",
            reponse_agent="answer",
            modele_agent="m",
            temps_reponse=0.0,
        )
        assert result is None

    def test_score_clamped_to_int(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db)
        verdict = JudgeVerdict(score=9.7, justification="great")
        prof = _make_professor(db, verdict)
        result = prof.evaluer_reponse(
            ticket_id=1,
            ticket_texte="t",
            reponse_agent="a",
            modele_agent="m",
            temps_reponse=0.0,
        )
        assert result["note"] == 10  # round(9.7) = 10

    def test_with_rca_diagnostic(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db)
        verdict = JudgeVerdict(score=6.0, justification="partial")
        prof = _make_professor(db, verdict)
        result = prof.evaluer_reponse(
            ticket_id=1,
            ticket_texte="VPN issue",
            reponse_agent="Check VPN",
            modele_agent="m",
            temps_reponse=1.0,
            diagnostic_rca="VPN tunnel inaccessible",
        )
        assert result["note"] == 6


class TestEvaluerTicketsEnAttente:
    def test_empty_queue_returns_zero(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db)
        verdict = JudgeVerdict(score=8.0, justification="ok")
        prof = _make_professor(db, verdict)
        count = prof.evaluer_tickets_en_attente()
        assert count == 0

    def test_evaluates_pending_tickets(self, tmp_path):
        db = str(tmp_path / "test.db")
        _init_db(db)
        # Insert an evaluation with note=0
        with sqlite3.connect(db) as conn:
            conn.execute(
                "INSERT INTO evaluations (ticket_id, modele, reponse_ia, temps_reponse_s, note_juge) "
                "VALUES (1, 'phi3', 'Restart client', 1.0, 0)"
            )
            conn.commit()

        verdict = JudgeVerdict(score=7.0, justification="fine")
        prof = _make_professor(db, verdict)
        # Patch RCAEngine to avoid ollama call
        with patch("src.bibops.evaluation.judges.llm_professor.RCAEngine") as MockRCA:
            MockRCA.return_value.analyser_cause_racine.return_value = "VPN cause"
            count = prof.evaluer_tickets_en_attente()
        assert count == 1

        with sqlite3.connect(db) as conn:
            row = conn.execute("SELECT note_juge FROM evaluations LIMIT 1").fetchone()
        assert row[0] == 7
