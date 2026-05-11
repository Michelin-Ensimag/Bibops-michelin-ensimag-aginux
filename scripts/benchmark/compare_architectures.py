#!/usr/bin/env python3
"""Compare "LLM Unique" (zero-shot) vs "Systeme Multi-Agents" on one CSV."""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import ollama

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agent.maestro import lancer_agent
from src.agent.tools import (
    chercher_dans_kb,
    chercher_documentation_technique,
    verifier_statut_serveur,
)
from src.bibops.evaluation.metrics.composite import CompositePolicy
from src.bibops.evaluation.registry import EvaluatorRegistry
from src.bibops.evaluation.metrics.greenops import calculate_carbon_footprint
from src.bibops.evaluation.judges.llm_professor import LLMProfessor
from src.bibops.evaluation.quality_evaluator import QualityEvaluator
from src.bibops.evaluation.result_schema import build_benchmark_payload
from src.bibops.evaluation.security_evaluator import SecurityLLMInspectorAdapter

DEFAULT_INPUT_CSV = PROJECT_ROOT / "data" / "raw" / "benchmark" / "tickets_scenario_1.csv"
DEFAULT_OUTPUT_JSON = PROJECT_ROOT / "data" / "outputs" / "benchmark" / "comparison_results.json"
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "databases" / "bibops.db"

# FinOps heuristic (USD / 1M tokens), aligned with existing llm_professor constants.
USD_INPUT_PER_1M_TOKENS = 2.50
USD_OUTPUT_PER_1M_TOKENS = 10.00


@dataclass
class ArchMetrics:
    label: str
    scores: list[float]
    total_latency_s: float
    prompt_tokens: int
    completion_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def avg_score(self) -> float:
        if not self.scores:
            return 0.0
        return round(statistics.mean(self.scores), 2)

    @property
    def cost_usd(self) -> float:
        return round(
            (self.prompt_tokens / 1_000_000.0) * USD_INPUT_PER_1M_TOKENS
            + (self.completion_tokens / 1_000_000.0) * USD_OUTPUT_PER_1M_TOKENS,
            6,
        )


def _resolve_input_csv(path: Path) -> Path:
    if path.exists():
        return path

    legacy_rel = Path("data/benchmark/tickets_scenario_1.csv")
    if str(path).endswith(str(legacy_rel)):
        fallback = PROJECT_ROOT / "data" / "raw" / "benchmark" / "tickets_scenario_1.csv"
        if fallback.exists():
            print(f"[INFO] CSV legacy introuvable, fallback auto vers: {fallback}")
            return fallback

    raise FileNotFoundError(f"CSV introuvable: {path}")


def _count_tokens_fallback(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


def _extract_ollama_text(response: dict[str, Any]) -> str:
    message = response.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content
    return ""


def _extract_ollama_token_usage(response: dict[str, Any]) -> tuple[int, int]:
    prompt = response.get("prompt_eval_count")
    completion = response.get("eval_count")
    if isinstance(prompt, int) and isinstance(completion, int):
        return prompt, completion

    usage = response.get("usage", {})
    if isinstance(usage, dict):
        p = usage.get("prompt_tokens")
        c = usage.get("completion_tokens")
        if isinstance(p, int) and isinstance(c, int):
            return p, c
        t = usage.get("total_tokens")
        if isinstance(t, int):
            return 0, t

    return 0, 0


def _evaluate_quality(
    evaluation_outputs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Normalize quality output from registry results."""
    quality = evaluation_outputs.get("quality", {})
    raw_score = quality.get("score", 0.0)
    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        score = 0.0
    score = max(0.0, min(10.0, score))

    return {
        "status": str(quality.get("status", "error")),
        "score": round(score, 2),
        "justification": str(quality.get("justification", "")),
        "error": str(quality.get("error", "")),
    }


def _evaluate_security(
    evaluation_outputs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Normalize security output from registry results."""
    security = evaluation_outputs.get("security", {})
    raw_score = security.get("security_score", 0.0)
    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        score = 0.0
    score = max(0.0, min(10.0, score))

    risks = security.get("risks", {})
    if not isinstance(risks, dict):
        risks = {}
    default_risks = {
        "pii": 1.0,
        "prompt_injection": 1.0,
        "secrets": 1.0,
        "malicious_urls": 1.0,
        "no_refusal": 1.0,
        "toxicity": 1.0,
    }
    for key in default_risks:
        try:
            default_risks[key] = float(risks.get(key, default_risks[key]))
        except (TypeError, ValueError):
            pass

    findings = security.get("findings", [])
    if not isinstance(findings, list):
        findings = []

    return {
        "status": str(security.get("status", "error")),
        "profile": str(security.get("profile", "p0_llminspector_aligned")),
        "security_score": round(score, 2),
        "blocked": bool(security.get("blocked", False)),
        "risk_avg": round(float(security.get("risk_avg", 1.0)), 4),
        "risks": {k: round(max(0.0, min(1.0, v)), 4) for k, v in default_risks.items()},
        "findings": findings,
        "error": str(security.get("error", "")),
    }


def _run_evaluators(
    registry: EvaluatorRegistry,
    ticket_text: str,
    answer_text: str,
    architecture: str,
) -> dict[str, dict[str, Any]]:
    """Run all registered evaluators for one answer."""
    return registry.run_all(
        {
            "ticket_text": ticket_text,
            "answer_text": answer_text,
            "diagnostic_rca": "Non disponible",
            "architecture": architecture,
        }
    )


def _print_comparison_table(rows: list[list[str]]) -> None:
    headers = ["Architecture", "Score Moyen", "Latence Totale (s)", "Coût USD", "Empreinte gCO2e"]
    widths = [len(h) for h in headers]
    for row in rows:
        for idx, value in enumerate(row):
            widths[idx] = max(widths[idx], len(value))

    def _fmt_line(values: list[str]) -> str:
        return " | ".join(v.ljust(widths[i]) for i, v in enumerate(values))

    separator = "-+-".join("-" * w for w in widths)

    print("\n" + "=" * 96)
    print("TABLEAU COMPARATIF FINAL")
    print("=" * 96)
    print(_fmt_line(headers))
    print(separator)
    for row in rows:
        print(_fmt_line(row))


def _print_release_decision(composite: dict[str, Any]) -> None:
    """Print composite scores and go/no-go release verdicts."""
    arches = composite.get("architectures", {})
    winner = composite.get("winner", "")
    print("\n" + "=" * 96)
    print("DECISION RELEASE (GO / NO-GO)")
    print("=" * 96)
    for arch in ("llm_unique", "systeme_multi_agents"):
        item = arches.get(arch, {})
        verdict = item.get("release_verdict", "FAIL")
        score = item.get("composite_score", 0.0)
        reasons = item.get("reasons", [])
        label = "LLM Unique" if arch == "llm_unique" else "Système Multi-Agents"
        print(f"{label:<24} -> composite={score:>6} /100 | verdict={verdict}")
        if reasons:
            print(f"  raisons: {', '.join(str(r) for r in reasons[:3])}")
    print(f"Winner policy: {winner}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Comparer LLM Unique (zero-shot) vs Systeme Multi-Agents (outils/RAG)."
    )
    parser.add_argument(
        "--input-csv",
        default=str(DEFAULT_INPUT_CSV),
        help="CSV de tickets (colonnes attendues: id, contexte, ticket).",
    )
    parser.add_argument(
        "--max-tickets",
        type=int,
        default=None,
        help="Limiter le nombre de tickets traités.",
    )
    parser.add_argument("--zero-shot-model", default="phi3:latest", help="Modele pour la voie zero-shot.")
    parser.add_argument("--agent-model", default="phi3:latest", help="Modele pour lancer_agent.")
    parser.add_argument("--judge-model", default="gpt-4o", help="Modele du juge LLM (proxy Copilot).")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="DB path requis par LLMProfessor.")
    parser.add_argument(
        "--hardware-type",
        default="local",
        choices=["local", "cloud"],
        help="Type de hardware pour l'estimation carbone.",
    )
    parser.add_argument(
        "--output-json",
        default=str(DEFAULT_OUTPUT_JSON),
        help="Chemin du JSON détaillé de sortie.",
    )
    args = parser.parse_args()

    csv_path = _resolve_input_csv(Path(args.input_csv))
    output_json = Path(args.output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)

    with open(csv_path, newline="", encoding="utf-8") as f:
        tickets = list(csv.DictReader(f))

    if args.max_tickets is not None and args.max_tickets > 0:
        tickets = tickets[: args.max_tickets]

    if not tickets:
        raise RuntimeError("Aucun ticket trouvé dans le CSV.")

    judge = LLMProfessor(db_path=args.db_path, modele_juge=args.judge_model)
    evaluator_registry = EvaluatorRegistry()
    evaluator_registry.register(QualityEvaluator(judge))
    evaluator_registry.register(SecurityLLMInspectorAdapter())
    outils = [verifier_statut_serveur, chercher_documentation_technique, chercher_dans_kb]

    llm_unique = ArchMetrics(
        label="LLM Unique",
        scores=[],
        total_latency_s=0.0,
        prompt_tokens=0,
        completion_tokens=0,
    )
    multi_agents = ArchMetrics(
        label="Système Multi-Agents",
        scores=[],
        total_latency_s=0.0,
        prompt_tokens=0,
        completion_tokens=0,
    )
    llm_unique_security_scores: list[float] = []
    multi_agents_security_scores: list[float] = []
    llm_unique_risk_sums: dict[str, float] = {
        "pii": 0.0,
        "prompt_injection": 0.0,
        "secrets": 0.0,
        "malicious_urls": 0.0,
        "no_refusal": 0.0,
        "toxicity": 0.0,
    }
    multi_agents_risk_sums: dict[str, float] = {
        "pii": 0.0,
        "prompt_injection": 0.0,
        "secrets": 0.0,
        "malicious_urls": 0.0,
        "no_refusal": 0.0,
        "toxicity": 0.0,
    }
    llm_unique_blocked = 0
    multi_agents_blocked = 0
    llm_unique_security_errors = 0
    multi_agents_security_errors = 0

    details: list[dict[str, Any]] = []

    print("=" * 96)
    print("COMPARAISON ARCHITECTURALE - BENCHMARK MICHELIN")
    print("=" * 96)
    print(f"CSV          : {csv_path}")
    print(f"Tickets      : {len(tickets)}")
    print(f"Zero-shot    : {args.zero_shot_model}")
    print(f"Agentique    : {args.agent_model}")
    print(f"Juge LLM     : {args.judge_model}")
    print(f"Hardware CO2 : {args.hardware_type}")

    for idx, row in enumerate(tickets, start=1):
        ticket_id = str(row.get("id", idx))
        contexte = str(row.get("contexte", "Tu es un assistant utile."))
        ticket_text = str(row.get("ticket") or row.get("texte_utilisateur") or "")

        if not ticket_text.strip():
            print(f"[WARN] Ticket vide ignoré (id={ticket_id}).")
            continue

        print(f"\n--- Ticket {idx}/{len(tickets)} | id={ticket_id} ---")

        # A) LLM Unique (zero-shot, sans outils)
        zs_answer = ""
        zs_prompt_tokens = 0
        zs_completion_tokens = 0
        zs_latency_s = 0.0
        zs_error = ""

        zs_start = time.perf_counter()
        try:
            zs_response = ollama.chat(
                model=args.zero_shot_model,
                messages=[
                    {"role": "system", "content": contexte},
                    {"role": "user", "content": ticket_text},
                ],
                options={"temperature": 0, "num_predict": 1024},
            )
            zs_latency_s = time.perf_counter() - zs_start
            zs_answer = _extract_ollama_text(zs_response)
            zs_prompt_tokens, zs_completion_tokens = _extract_ollama_token_usage(zs_response)
        except Exception as exc:
            zs_latency_s = time.perf_counter() - zs_start
            zs_error = str(exc)
            zs_answer = f"ERREUR_ZERO_SHOT: {exc}"

        if (zs_prompt_tokens + zs_completion_tokens) == 0:
            fallback = _count_tokens_fallback(ticket_text) + _count_tokens_fallback(zs_answer)
            zs_completion_tokens = max(0, fallback)

        llm_unique.total_latency_s += zs_latency_s
        llm_unique.prompt_tokens += zs_prompt_tokens
        llm_unique.completion_tokens += zs_completion_tokens

        # B) Système Multi-Agents (lancer_agent + outils/RAG)
        ag_answer = ""
        ag_prompt_tokens = 0
        ag_completion_tokens = 0
        ag_latency_s = 0.0
        ag_error = ""
        ag_tool_calls = 0

        try:
            ag_result = lancer_agent(
                contexte=contexte,
                ticket_utilisateur=ticket_text,
                outils_disponibles=outils,
                modele=args.agent_model,
                return_trace=True,
                structured_output=True,
            )
            ag_answer = str(ag_result.get("reponse_finale", ""))
            trace = ag_result.get("trace", {})
            ag_latency_s = float(trace.get("total_duree_ms", 0)) / 1000.0

            llm_turns = trace.get("llm_turns", [])
            for turn in llm_turns:
                ag_prompt_tokens += int(turn.get("prompt_tokens") or 0)
                ag_completion_tokens += int(turn.get("completion_tokens") or 0)

            ag_tool_calls = len(trace.get("tool_calls", []))
        except Exception as exc:
            ag_error = str(exc)
            ag_answer = f"ERREUR_AGENTIQUE: {exc}"

        if (ag_prompt_tokens + ag_completion_tokens) == 0:
            fallback = _count_tokens_fallback(ticket_text) + _count_tokens_fallback(ag_answer)
            ag_completion_tokens = max(0, fallback)

        multi_agents.total_latency_s += ag_latency_s
        multi_agents.prompt_tokens += ag_prompt_tokens
        multi_agents.completion_tokens += ag_completion_tokens

        # C) Evaluation (qualité + sécurité) via registry d'évaluateurs
        zs_eval_outputs = _run_evaluators(
            registry=evaluator_registry,
            ticket_text=ticket_text,
            answer_text=zs_answer,
            architecture="llm_unique",
        )
        ag_eval_outputs = _run_evaluators(
            registry=evaluator_registry,
            ticket_text=ticket_text,
            answer_text=ag_answer,
            architecture="systeme_multi_agents",
        )
        zs_quality = _evaluate_quality(zs_eval_outputs)
        ag_quality = _evaluate_quality(ag_eval_outputs)
        zs_security = _evaluate_security(zs_eval_outputs)
        ag_security = _evaluate_security(ag_eval_outputs)
        zs_score = float(zs_quality["score"])
        ag_score = float(ag_quality["score"])

        llm_unique.scores.append(zs_score)
        multi_agents.scores.append(ag_score)
        llm_unique_security_scores.append(float(zs_security["security_score"]))
        multi_agents_security_scores.append(float(ag_security["security_score"]))
        if zs_security["blocked"]:
            llm_unique_blocked += 1
        if ag_security["blocked"]:
            multi_agents_blocked += 1
        if zs_security["status"] != "ok":
            llm_unique_security_errors += 1
        if ag_security["status"] != "ok":
            multi_agents_security_errors += 1
        for key in llm_unique_risk_sums:
            llm_unique_risk_sums[key] += float(zs_security["risks"].get(key, 1.0))
            multi_agents_risk_sums[key] += float(ag_security["risks"].get(key, 1.0))

        print(
            f"LLM Unique -> score={zs_score}/10 | latence={zs_latency_s:.2f}s | "
            f"tokens={zs_prompt_tokens + zs_completion_tokens} | sec={zs_security['security_score']}/10"
        )
        print(
            f"Multi-Agents -> score={ag_score}/10 | latence={ag_latency_s:.2f}s | "
            f"tokens={ag_prompt_tokens + ag_completion_tokens} | tools={ag_tool_calls} | sec={ag_security['security_score']}/10"
        )

        details.append(
            {
                "ticket_id": ticket_id,
                "ticket": ticket_text,
                "llm_unique": {
                    "answer": zs_answer,
                    "score": zs_score,
                    "justification": zs_quality["justification"],
                    "quality": zs_quality,
                    "security": zs_security,
                    "latency_s": round(zs_latency_s, 4),
                    "prompt_tokens": zs_prompt_tokens,
                    "completion_tokens": zs_completion_tokens,
                    "total_tokens": zs_prompt_tokens + zs_completion_tokens,
                    "error": zs_error,
                },
                "multi_agents": {
                    "answer": ag_answer,
                    "score": ag_score,
                    "justification": ag_quality["justification"],
                    "quality": ag_quality,
                    "security": ag_security,
                    "latency_s": round(ag_latency_s, 4),
                    "prompt_tokens": ag_prompt_tokens,
                    "completion_tokens": ag_completion_tokens,
                    "total_tokens": ag_prompt_tokens + ag_completion_tokens,
                    "tool_calls": ag_tool_calls,
                    "error": ag_error,
                },
            }
        )

    llm_unique_carbon = calculate_carbon_footprint(llm_unique.total_tokens, args.hardware_type)
    multi_agents_carbon = calculate_carbon_footprint(multi_agents.total_tokens, args.hardware_type)

    summary = {
        "llm_unique": {
            "score_moyen": llm_unique.avg_score,
            "latence_totale_s": round(llm_unique.total_latency_s, 4),
            "cout_usd": llm_unique.cost_usd,
            "empreinte_gco2e": llm_unique_carbon["gCO2e"],
            "energy_kwh": llm_unique_carbon["energy_kwh"],
            "prompt_tokens": llm_unique.prompt_tokens,
            "completion_tokens": llm_unique.completion_tokens,
            "total_tokens": llm_unique.total_tokens,
        },
        "systeme_multi_agents": {
            "score_moyen": multi_agents.avg_score,
            "latence_totale_s": round(multi_agents.total_latency_s, 4),
            "cout_usd": multi_agents.cost_usd,
            "empreinte_gco2e": multi_agents_carbon["gCO2e"],
            "energy_kwh": multi_agents_carbon["energy_kwh"],
            "prompt_tokens": multi_agents.prompt_tokens,
            "completion_tokens": multi_agents.completion_tokens,
            "total_tokens": multi_agents.total_tokens,
        },
    }
    quality_summary = {
        "llm_unique": {
            "score_moyen": llm_unique.avg_score,
            "nb_reponses_notees": len(llm_unique.scores),
        },
        "systeme_multi_agents": {
            "score_moyen": multi_agents.avg_score,
            "nb_reponses_notees": len(multi_agents.scores),
        },
    }
    llm_unique_count = max(1, len(llm_unique_security_scores))
    multi_agents_count = max(1, len(multi_agents_security_scores))
    security_summary = {
        "llm_unique": {
            "security_score_moyen": round(statistics.mean(llm_unique_security_scores), 2)
            if llm_unique_security_scores
            else 0.0,
            "blocked_count": llm_unique_blocked,
            "error_count": llm_unique_security_errors,
            "risks_moyens": {
                key: round(value / llm_unique_count, 4)
                for key, value in llm_unique_risk_sums.items()
            },
        },
        "systeme_multi_agents": {
            "security_score_moyen": round(statistics.mean(multi_agents_security_scores), 2)
            if multi_agents_security_scores
            else 0.0,
            "blocked_count": multi_agents_blocked,
            "error_count": multi_agents_security_errors,
            "risks_moyens": {
                key: round(value / multi_agents_count, 4)
                for key, value in multi_agents_risk_sums.items()
            },
        },
    }
    composite_policy = CompositePolicy()
    composite_summary = composite_policy.evaluate(
        summary=summary,
        quality=quality_summary,
        security=security_summary,
    )

    rows = [
        [
            "LLM Unique",
            f"{summary['llm_unique']['score_moyen']:.2f}",
            f"{summary['llm_unique']['latence_totale_s']:.2f}",
            f"{summary['llm_unique']['cout_usd']:.6f}",
            f"{summary['llm_unique']['empreinte_gco2e']:.6f}",
        ],
        [
            "Système Multi-Agents",
            f"{summary['systeme_multi_agents']['score_moyen']:.2f}",
            f"{summary['systeme_multi_agents']['latence_totale_s']:.2f}",
            f"{summary['systeme_multi_agents']['cout_usd']:.6f}",
            f"{summary['systeme_multi_agents']['empreinte_gco2e']:.6f}",
        ],
    ]
    _print_comparison_table(rows)
    _print_release_decision(composite_summary)

    payload = build_benchmark_payload(
        config={
            "input_csv": str(csv_path),
            "max_tickets": args.max_tickets,
            "zero_shot_model": args.zero_shot_model,
            "agent_model": args.agent_model,
            "judge_model": args.judge_model,
            "hardware_type": args.hardware_type,
            "enabled_evaluators": ["quality", "security"],
            "composite_policy_version": composite_summary.get("policy_version", "1.0.0"),
            "pricing_usd_per_1m_tokens": {
                "input": USD_INPUT_PER_1M_TOKENS,
                "output": USD_OUTPUT_PER_1M_TOKENS,
            },
        },
        summary=summary,
        quality=quality_summary,
        security=security_summary,
        composite=composite_summary,
        details=details,
    )

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"\n[OK] Résultats détaillés sauvegardés dans: {output_json}")


if __name__ == "__main__":
    main()
