#!/usr/bin/env python3
"""Compare "LLM Unique" (zero-shot) vs "Systeme Multi-Agents" on one CSV."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.agent.maestro import lancer_agent
from src.agent.tools import (
    chercher_dans_kb,
    chercher_documentation_technique,
    verifier_statut_serveur,
)
from src.bibops.evaluation.judges.llm_professor import LLMProfessor
from src.bibops.evaluation.metrics.composite import CompositePolicy
from src.bibops.evaluation.metrics.greenops import calculate_carbon_footprint
from src.bibops.evaluation.quality_evaluator import QualityEvaluator
from src.bibops.evaluation.registry import EvaluatorRegistry
from src.bibops.evaluation.result_schema import build_benchmark_payload
from src.bibops.evaluation.security_evaluator import SecurityLLMInspectorAdapter
from src.common.chat_models import call_chat_model
from src.common.text import contains_timeout, load_tickets_csv
from src.common.config import (
    DEFAULT_AGENT_MODEL,
    DEFAULT_AGENT_PROVIDER,
    DEFAULT_JUDGE_MODEL,
    DEFAULT_ZERO_SHOT_MODEL,
    DEFAULT_ZERO_SHOT_PROVIDER,
    validate_chat_model,
    validate_judge_model,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT_CSV = PROJECT_ROOT / "data" / "inputs" / "benchmark" / "tickets_scenario_1.csv"
DEFAULT_OUTPUT_JSON = PROJECT_ROOT / "data" / "outputs" / "benchmark" / "comparison_results.json"
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "databases" / "bibops.db"

# FinOps heuristic (USD / 1M tokens), aligned with existing llm_professor constants.
USD_INPUT_PER_1M_TOKENS = 2.50
USD_OUTPUT_PER_1M_TOKENS = 10.00
DOMAIN_CHOICES = ("all", "it", "rh", "juridique", "finance", "autre", "non-it")
DOMAIN_LABELS = {
    "it": "IT",
    "rh": "RH",
    "juridique": "Juridique",
    "finance": "Finance/Voyage",
    "autre": "Autre",
}


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

    legacy_paths = (
        Path("data/benchmark/tickets_scenario_1.csv"),
        Path("data/raw/benchmark/tickets_scenario_1.csv"),
    )
    if any(str(path).endswith(str(legacy_rel)) for legacy_rel in legacy_paths):
        fallback = PROJECT_ROOT / "data" / "inputs" / "benchmark" / "tickets_scenario_1.csv"
        if fallback.exists():
            print(f"[INFO] CSV legacy introuvable, fallback auto vers: {fallback}")
            return fallback

    raise FileNotFoundError(f"CSV introuvable: {path}")


def _classify_domain(contexte: str, ticket: str) -> str:
    text = f"{contexte} {ticket}".lower()
    if "technicien support it" in text or "support it" in text:
        return "it"
    if "ressources humaines" in text or "expert rh" in text or "outil rh" in text:
        return "rh"
    if "juriste" in text or "juridique" in text:
        return "juridique"
    if "finance" in text or "voyage" in text or "note de frais" in text:
        return "finance"
    return "autre"


def _filter_by_domain(rows: list[dict[str, str]], selected_domain: str) -> list[dict[str, str]]:
    if selected_domain == "all":
        return rows

    filtered = []
    for row in rows:
        domain = _classify_domain(
            str(row.get("contexte", "")),
            str(row.get("ticket") or row.get("texte_utilisateur") or ""),
        )
        if selected_domain == "non-it":
            if domain != "it":
                filtered.append(row)
        elif domain == selected_domain:
            filtered.append(row)
    return filtered


def _count_statuses(tool_calls: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for call in tool_calls:
        status = str(call.get("statut") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


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
    if winner:
        print(f"Winner policy: {winner}")
    else:
        print("Winner policy: NO WINNER (toutes les architectures ont échoué les gates)")
    winners_by_metric = composite.get("winners_by_metric", {})
    if isinstance(winners_by_metric, dict) and winners_by_metric:
        print(
            "Winners métriques: "
            f"quality={winners_by_metric.get('quality')}, "
            f"latency={winners_by_metric.get('latency')}, "
            f"cost={winners_by_metric.get('cost')}, "
            f"composite={winners_by_metric.get('composite')}"
        )


def _winner_by_metric(values: dict[str, float], *, lower_is_better: bool = False) -> str | None:
    if not values:
        return None
    fn = min if lower_is_better else max
    return fn(values, key=values.get)


def _compute_winners_by_metric(summary: dict[str, Any], composite: dict[str, Any]) -> dict[str, str | None]:
    arches = [arch for arch in ("llm_unique", "systeme_multi_agents") if arch in summary]
    composite_arches = composite.get("architectures", {}) if isinstance(composite, dict) else {}
    return {
        "quality": _winner_by_metric({arch: float(summary[arch].get("score_moyen", 0.0)) for arch in arches}),
        "latency": _winner_by_metric(
            {arch: float(summary[arch].get("latence_totale_s", 0.0)) for arch in arches},
            lower_is_better=True,
        ),
        "cost": _winner_by_metric(
            {arch: float(summary[arch].get("cout_usd", 0.0)) for arch in arches},
            lower_is_better=True,
        ),
        "composite": _winner_by_metric(
            {arch: float(composite_arches.get(arch, {}).get("composite_score", 0.0)) for arch in arches}
        ),
    }


def _build_domain_summary(details: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_domain: dict[str, list[dict[str, Any]]] = {}
    for item in details:
        by_domain.setdefault(str(item.get("domain", "autre")), []).append(item)

    output: dict[str, dict[str, Any]] = {}
    for domain, rows in sorted(by_domain.items()):
        n = max(1, len(rows))
        zs_scores = [float(row["llm_unique"]["score"]) for row in rows]
        ag_scores = [float(row["multi_agents"]["score"]) for row in rows]
        deltas = [ag - zs for zs, ag in zip(zs_scores, ag_scores, strict=False)]
        tool_call_total = sum(int(row["multi_agents"].get("tool_calls", 0)) for row in rows)
        tool_ticket_count = sum(1 for row in rows if int(row["multi_agents"].get("tool_calls", 0)) > 0)
        output[domain] = {
            "label": DOMAIN_LABELS.get(domain, domain),
            "ticket_count": len(rows),
            "llm_unique_score_moyen": round(sum(zs_scores) / n, 2),
            "systeme_multi_agents_score_moyen": round(sum(ag_scores) / n, 2),
            "delta_agent_vs_zero_shot": round(sum(deltas) / n, 2),
            "agent_wins": sum(1 for delta in deltas if delta > 0),
            "zero_shot_wins": sum(1 for delta in deltas if delta < 0),
            "ties": sum(1 for delta in deltas if delta == 0),
            "agent_tool_call_total": tool_call_total,
            "agent_tool_use_rate": round(tool_ticket_count / n, 4),
            "agent_fallback_count": sum(
                1 for row in rows if "fallback" in str(row["multi_agents"].get("trace_outcome", ""))
            ),
            "zero_shot_timeout_count": sum(
                1
                for row in rows
                if contains_timeout(str(row["llm_unique"].get("error", "")))
                or contains_timeout(str(row["llm_unique"].get("answer", "")))
            ),
        }
    return output


def _build_diagnostics(details: list[dict[str, Any]]) -> dict[str, Any]:
    n = max(1, len(details))
    deltas = [float(item["multi_agents"]["score"]) - float(item["llm_unique"]["score"]) for item in details]
    tool_status_totals: dict[str, int] = {}
    for item in details:
        for status, count in item["multi_agents"].get("tool_status_counts", {}).items():
            tool_status_totals[status] = tool_status_totals.get(status, 0) + int(count)

    zs_timeout_count = sum(
        1
        for item in details
        if contains_timeout(str(item["llm_unique"].get("error", "")))
        or contains_timeout(str(item["llm_unique"].get("answer", "")))
    )
    ag_timeout_count = sum(
        1
        for item in details
        if contains_timeout(str(item["multi_agents"].get("error", "")))
        or "timeout" in str(item["multi_agents"].get("trace_outcome", ""))
    )
    agent_tool_ticket_count = sum(1 for item in details if int(item["multi_agents"].get("tool_calls", 0)) > 0)
    agent_tool_call_total = sum(int(item["multi_agents"].get("tool_calls", 0)) for item in details)
    return {
        "ticket_count": len(details),
        "agent_wins": sum(1 for delta in deltas if delta > 0),
        "zero_shot_wins": sum(1 for delta in deltas if delta < 0),
        "ties": sum(1 for delta in deltas if delta == 0),
        "avg_score_delta_agent_minus_zero_shot": round(sum(deltas) / n, 2),
        "llm_unique": {
            "error_count": sum(1 for item in details if bool(item["llm_unique"].get("error"))),
            "timeout_count": zs_timeout_count,
            "score_lt_3_count": sum(1 for item in details if float(item["llm_unique"]["score"]) < 3.0),
            "score_ge_7_count": sum(1 for item in details if float(item["llm_unique"]["score"]) >= 7.0),
        },
        "systeme_multi_agents": {
            "error_count": sum(1 for item in details if bool(item["multi_agents"].get("error"))),
            "timeout_count": ag_timeout_count,
            "fallback_count": sum(
                1 for item in details if "fallback" in str(item["multi_agents"].get("trace_outcome", ""))
            ),
            "timeout_fallback_count": sum(
                1 for item in details if str(item["multi_agents"].get("trace_outcome", "")) == "timeout_fallback"
            ),
            "empty_answer_repair_count": sum(
                int(item["multi_agents"].get("empty_answer_repair_count", 0)) for item in details
            ),
            "forced_initial_tool_count": sum(
                1 for item in details if bool(item["multi_agents"].get("forced_initial_tool", False))
            ),
            "tool_ticket_count": agent_tool_ticket_count,
            "tool_call_total": agent_tool_call_total,
            "tool_use_rate": round(agent_tool_ticket_count / n, 4),
            "tool_status_counts": tool_status_totals,
            "unknown_tool_count": tool_status_totals.get("unknown_tool", 0),
            "invalid_tool_argument_count": tool_status_totals.get("invalid_argument", 0),
            "score_lt_3_count": sum(1 for item in details if float(item["multi_agents"]["score"]) < 3.0),
            "score_ge_7_count": sum(1 for item in details if float(item["multi_agents"]["score"]) >= 7.0),
        },
    }


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
    parser.add_argument(
        "--domain",
        default="all",
        choices=DOMAIN_CHOICES,
        help="Filtrer les tickets par domaine avant --max-tickets.",
    )
    parser.add_argument("--zero-shot-provider", default=DEFAULT_ZERO_SHOT_PROVIDER, choices=["ollama", "copilot"])
    parser.add_argument("--zero-shot-model", default=DEFAULT_ZERO_SHOT_MODEL, help="Modele pour la voie zero-shot.")
    parser.add_argument("--agent-provider", default=DEFAULT_AGENT_PROVIDER, choices=["ollama", "copilot"])
    parser.add_argument("--agent-model", default=DEFAULT_AGENT_MODEL, help="Modele pour lancer_agent.")
    parser.add_argument(
        "--agent-max-iterations",
        type=int,
        default=3,
        help="Nombre maximum de tours ReAct pour le système multi-agents.",
    )
    parser.add_argument("--judge-model", default=DEFAULT_JUDGE_MODEL, help="Modele du juge LLM (proxy Copilot).")
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
    try:
        validate_judge_model(args.judge_model)
        validate_chat_model(args.zero_shot_provider, args.zero_shot_model, role="zero-shot model")
        validate_chat_model(args.agent_provider, args.agent_model, role="agent model")
    except ValueError as exc:
        parser.error(str(exc))

    csv_path = _resolve_input_csv(Path(args.input_csv))
    output_json = Path(args.output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)

    tickets_all = load_tickets_csv(str(csv_path))
    tickets = _filter_by_domain(tickets_all, args.domain)
    if args.max_tickets is not None and args.max_tickets > 0:
        tickets = tickets[: args.max_tickets]

    if not tickets:
        raise RuntimeError(f"Aucun ticket trouvé dans le CSV pour domain={args.domain}.")

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
    print(f"Tickets      : {len(tickets)} / {len(tickets_all)}")
    print(f"Domaine      : {args.domain}")
    print(f"Zero-shot    : {args.zero_shot_provider}:{args.zero_shot_model}")
    print(f"Agentique    : {args.agent_provider}:{args.agent_model}")
    print(f"Max iter ag. : {args.agent_max_iterations}")
    print(f"Juge LLM     : {args.judge_model}")
    print(f"Hardware CO2 : {args.hardware_type}")

    for idx, row in enumerate(tickets, start=1):
        ticket_id = str(row.get("id", idx))
        contexte = str(row.get("contexte", "Tu es un assistant utile."))
        ticket_text = str(row.get("ticket") or row.get("texte_utilisateur") or "")
        domain = _classify_domain(contexte, ticket_text)

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
            zs_response = call_chat_model(
                provider=args.zero_shot_provider,
                model=args.zero_shot_model,
                messages=[
                    {"role": "system", "content": contexte},
                    {"role": "user", "content": ticket_text},
                ],
                temperature=0,
                max_tokens=1024,
            )
            zs_latency_s = time.perf_counter() - zs_start
            zs_answer = zs_response.text
            zs_prompt_tokens, zs_completion_tokens = zs_response.prompt_tokens, zs_response.completion_tokens
        except Exception as exc:
            zs_latency_s = time.perf_counter() - zs_start
            zs_error = str(exc)
            zs_answer = f"ERREUR_ZERO_SHOT: {exc}"

        if (zs_prompt_tokens + zs_completion_tokens) == 0:
            zs_completion_tokens = max(0, len(ticket_text.split()) + len(zs_answer.split()))

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
        ag_trace: dict[str, Any] = {}
        ag_tool_status_counts: dict[str, int] = {}

        try:
            ag_result = lancer_agent(
                contexte=contexte,
                ticket_utilisateur=ticket_text,
                outils_disponibles=outils,
                modele=args.agent_model,
                modele_provider=args.agent_provider,
                max_iterations=args.agent_max_iterations,
                return_trace=True,
                structured_output=True,
                force_initial_tool=True,
                deterministic_tool_answer=True,
            )
            ag_answer = str(ag_result.get("reponse_finale", ""))
            trace = ag_result.get("trace", {})
            ag_trace = trace if isinstance(trace, dict) else {}
            ag_latency_s = float(trace.get("total_duree_ms", 0)) / 1000.0

            llm_turns = trace.get("llm_turns", [])
            for turn in llm_turns:
                ag_prompt_tokens += int(turn.get("prompt_tokens") or 0)
                ag_completion_tokens += int(turn.get("completion_tokens") or 0)

            ag_tool_calls = len(trace.get("tool_calls", []))
            ag_tool_status_counts = _count_statuses(trace.get("tool_calls", []))
        except Exception as exc:
            ag_error = str(exc)
            ag_answer = f"ERREUR_AGENTIQUE: {exc}"

        if (ag_prompt_tokens + ag_completion_tokens) == 0:
            ag_completion_tokens = max(0, len(ticket_text.split()) + len(ag_answer.split()))

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
                "domain": domain,
                "domain_label": DOMAIN_LABELS.get(domain, domain),
                "contexte": contexte,
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
                    "tool_status_counts": ag_tool_status_counts,
                    "tool_trace": ag_trace.get("tool_calls", []),
                    "llm_turn_count": len(ag_trace.get("llm_turns", [])),
                    "trace_outcome": str(ag_trace.get("outcome", "")),
                    "routing_hint": ag_trace.get("routing_hint", {}),
                    "forced_initial_tool": bool(ag_trace.get("forced_initial_tool", False)),
                    "empty_answer_repair_count": int(ag_trace.get("empty_answer_repair_count", 0) or 0),
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
    composite_summary["winners_by_metric"] = _compute_winners_by_metric(summary, composite_summary)
    domain_summary = _build_domain_summary(details)
    diagnostics_summary = _build_diagnostics(details)

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
            "selected_domain": args.domain,
            "available_domains": list(DOMAIN_CHOICES),
            "zero_shot_provider": args.zero_shot_provider,
            "zero_shot_model": args.zero_shot_model,
            "agent_provider": args.agent_provider,
            "agent_model": args.agent_model,
            "agent_max_iterations": args.agent_max_iterations,
            "agent_force_initial_tool": True,
            "agent_deterministic_tool_answer": True,
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
    payload["domain_summary"] = domain_summary
    payload["diagnostics"] = diagnostics_summary

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"\n[OK] Résultats détaillés sauvegardés dans: {output_json}")


if __name__ == "__main__":
    main()
