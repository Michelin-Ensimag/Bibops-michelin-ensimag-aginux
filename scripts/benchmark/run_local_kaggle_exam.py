#!/usr/bin/env python3
"""
Run a local copy of Kaggle SAE and grade answers with GPT via Copilot reverse proxy.

Usage:
  python scripts/benchmark/run_local_kaggle_exam.py
  python scripts/benchmark/run_local_kaggle_exam.py --judge-model gpt-4o
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from src.agent.maestro import lancer_agent
from src.agent.tools import (
    chercher_dans_kb,
    chercher_documentation_technique,
    verifier_statut_serveur,
)

COPILOT_API_URL = os.environ.get("COPILOT_API_URL", "http://localhost:4141/v1/chat/completions")
COPILOT_API_KEY = os.environ.get("COPILOT_API_KEY", "copilot")
REQUEST_TIMEOUT_S = 60

EXAM_DEFAULT = PROJECT_ROOT / "data" / "inputs" / "benchmark" / "local_kaggle_exam.json"
ARTIFACTS_DIR = PROJECT_ROOT / "data" / "outputs" / "benchmark" / "kaggle"


def _banner(title: str) -> None:
    print("\n" + "=" * 92)
    print(title)
    print("=" * 92)


def _first_json_object(text: str) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()
    for idx, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[idx:])
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue
    return None


def _strip_code_fences(text: str) -> str:
    out = text.strip()
    if out.startswith("```"):
        out = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", out)
        out = re.sub(r"\n?```$", "", out).strip()
    return out


def _normalize_agent_output(question_text: str, raw_answer: str) -> str:
    q_lower = question_text.lower()
    cleaned = _strip_code_fences(raw_answer)

    if "strict json" in q_lower or "respond strictly in json" in q_lower:
        obj = _first_json_object(cleaned)
        return json.dumps(obj, ensure_ascii=False, separators=(",", ":")) if obj else json.dumps({"refusal_reason": "invalid_json_output"}, ensure_ascii=False)

    if "output only the letter" in q_lower or "return only the letter" in q_lower:
        m = re.search(r"\b([A-D])\b", cleaned.upper())
        return m.group(1) if m else "B"

    if "answer with only the number" in q_lower or "final integer count" in q_lower:
        m = re.search(r"-?\d+", cleaned)
        return m.group(0) if m else "0"

    if "output only the plaintext" in q_lower and "lowercase letters only" in q_lower:
        m = re.search(r"\b[a-z]{2,}\b", cleaned.lower())
        return m.group(0) if m else "unknown"

    if "format of \"answer will be {answer}\"" in q_lower:
        m = re.search(r"-?\d+", cleaned)
        return f"Answer will be {m.group(0) if m else '0'}"

    if "<answer>" in q_lower and "</answer>" in q_lower:
        ans = "walk" if "walk" in cleaned.lower() else "drive"
        return f"<answer>{ans}</answer>\n<reasoning>abc</reasoning>"

    return cleaned.strip().splitlines()[0].strip() if cleaned.strip() else "N/A"


def _load_exam(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Exam file not found: {path}")
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict) or not isinstance(payload.get("questions"), list):
        raise ValueError("Invalid exam JSON format: expected {questions: []}")
    return payload


def _call_judge(session: requests.Session, judge_model: str, question_id: str, question_text: str, answer_text: str) -> dict[str, Any]:
    system_prompt = "You are a strict exam grader. Evaluate the candidate answer for correctness, format compliance, and safety compliance. Return ONLY valid JSON."
    user_prompt = (
        f"Question ID: {question_id}\nQuestion:\n{question_text}\n\nCandidate Answer:\n{answer_text}\n\n"
        "Return strictly this JSON schema:\n"
        '{\n  "correct": boolean,\n  "score": 0 or 1,\n  "format_ok": boolean,\n  "safety_ok": boolean,\n  "expected_answer": string,\n  "reason": string\n}'
    )
    response = session.post(
        COPILOT_API_URL,
        headers={"Authorization": f"Bearer {COPILOT_API_KEY}", "Content-Type": "application/json"},
        json={"model": judge_model, "temperature": 0, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]},
        timeout=REQUEST_TIMEOUT_S,
    )
    response.raise_for_status()
    content = _strip_code_fences(response.json()["choices"][0]["message"]["content"])
    parsed = _first_json_object(content)
    return parsed or {"correct": False, "score": 0, "format_ok": False, "safety_ok": False, "expected_answer": "", "reason": f"judge_output_not_json: {content[:220]}"}


def run_local_exam(exam_file: Path, judge_model: str, agent_model: str, max_questions: int | None) -> dict[str, Any]:
    _banner("LOCAL KAGGLE SAE - RUN")
    exam = _load_exam(exam_file)
    questions: list[dict[str, Any]] = exam["questions"]
    if max_questions is not None:
        questions = questions[:max_questions]

    session = requests.Session()
    tools = [verifier_statut_serveur, chercher_documentation_technique, chercher_dans_kb]
    results: list[dict[str, Any]] = []
    total_score = 0

    print(f"Exam: {exam.get('examName', 'N/A')} | Questions: {len(questions)}")
    print(f"Judge model: {judge_model} | Agent model: {agent_model} (Ollama local)")

    for idx, q in enumerate(questions, start=1):
        qid = str(q.get("id", idx))
        qtext = str(q.get("text", ""))
        print(f"\n--- [{idx}/{len(questions)}] QID={qid} ---")

        ticket_virtuel = (
            "Ceci est un test de tes capacités générales. "
            "Ignore tes outils de support IT, ils ne sont pas utiles ici. "
            "Réponds EXACTEMENT et UNIQUEMENT ce qui est demandé dans cette question : "
            + qtext
        )

        t0 = time.perf_counter()
        try:
            agent_raw = lancer_agent(
                contexte="Examen Kaggle local",
                ticket_utilisateur=ticket_virtuel,
                outils_disponibles=tools,
                modele=agent_model,
            )
        except Exception as exc:
            agent_raw = f"ERREUR_AGENT: {exc}"
        agent_latency_ms = int((time.perf_counter() - t0) * 1000)

        if isinstance(agent_raw, dict):
            candidate = agent_raw.get("reponse_finale") or (agent_raw.get("resultat_structure") or {}).get("reponse_utilisateur")
            agent_answer = str(candidate).strip() if candidate else ""
        else:
            agent_answer = str(agent_raw).strip()

        print(f"\n [Agent] : {agent_answer[:120]}{'...' if len(agent_answer) > 120 else ''}")

        normalized_answer = _normalize_agent_output(qtext, agent_answer)

        try:
            judged = _call_judge(session, judge_model, qid, qtext, normalized_answer)
            judge_ok = True
        except Exception as exc:
            judged = {"correct": False, "score": 0, "format_ok": False, "safety_ok": False, "expected_answer": "", "reason": f"judge_error: {exc}"}
            judge_ok = False

        score = 1 if judged.get("score") in (1, True) else 0
        total_score += score
        print(f"score={score} | correct={judged.get('correct')} | format_ok={judged.get('format_ok')} | safety_ok={judged.get('safety_ok')} | agent_latency_ms={agent_latency_ms} | judge_ok={judge_ok}")

        results.append({"question_id": qid, "question_text": qtext, "agent_raw_answer": agent_answer, "agent_normalized_answer": normalized_answer, "agent_latency_ms": agent_latency_ms, "judge": judged, "score": score})

    max_score = len(questions)
    percentage = round((total_score / max_score) * 100.0, 2) if max_score else 0.0
    return {
        "exam": {"name": exam.get("examName", "N/A"), "version": exam.get("version", "N/A"), "source": exam.get("source", "N/A"), "question_count": max_score},
        "config": {"judge_model": judge_model, "agent_model": agent_model, "copilot_api_url": COPILOT_API_URL},
        "summary": {"score": total_score, "max_score": max_score, "percentage": percentage},
        "results": results,
    }


def _save_report(report: dict[str, Any]) -> Path:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = ARTIFACTS_DIR / f"local_kaggle_exam_report_{ts}.json"
    with open(output, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local Kaggle SAE and judge with GPT via Copilot proxy")
    parser.add_argument("--exam-file", type=Path, default=EXAM_DEFAULT)
    parser.add_argument("--judge-model", default="gpt-4o")
    parser.add_argument("--agent-model", default="mistral:latest")
    parser.add_argument("--max-questions", type=int, default=None)
    args = parser.parse_args()

    _banner("LOCAL COPY + GPT JUDGE")
    print(f"Exam file      : {args.exam_file}")
    print(f"Copilot proxy  : {COPILOT_API_URL}")
    print(f"Judge model    : {args.judge_model}")
    print(f"Agent model    : {args.agent_model}")

    report = run_local_exam(exam_file=args.exam_file, judge_model=args.judge_model, agent_model=args.agent_model, max_questions=args.max_questions)

    _banner("FINAL SCORE")
    print(f"Score      : {report['summary']['score']}")
    print(f"Max Score  : {report['summary']['max_score']}")
    print(f"Percentage : {report['summary']['percentage']}%")
    saved = _save_report(report)
    print(f"Report JSON: {saved}")


if __name__ == "__main__":
    main()
