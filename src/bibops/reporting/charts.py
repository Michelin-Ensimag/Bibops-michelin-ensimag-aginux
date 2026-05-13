"""Generate report-ready PNG charts from BibOps JSON artefacts."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "bibops-matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.common.config import BASE_DIR

DEFAULT_BENCHMARK_DIR = BASE_DIR / "data" / "outputs" / "benchmark"
DEFAULT_CHARTS_DIR = DEFAULT_BENCHMARK_DIR / "charts"
DEFAULT_COVERAGE_JSON = BASE_DIR / "data" / "outputs" / "coverage.json"
DEFAULT_EVAL_BANK_DIR = BASE_DIR / "data" / "outputs" / "eval_bank"

COLORS = {
    "blue": "#2563eb",
    "green": "#16a34a",
    "red": "#dc2626",
    "orange": "#ea580c",
    "purple": "#7c3aed",
    "cyan": "#0891b2",
    "gray": "#64748b",
    "slate": "#334155",
}


def _load_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _latest_json(directory: Path, pattern: str) -> Path | None:
    if not directory.exists():
        return None
    files = sorted(directory.glob(pattern), key=lambda item: item.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _listify(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _save(fig: plt.Figure, path: Path, outputs: list[Path]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    outputs.append(path)


def _missing(path: Path, warnings: list[str]) -> None:
    warnings.append(f"missing source: {path}")


def _bar_labels(ax: plt.Axes, fmt: str = "{:.2f}") -> None:
    for patch in ax.patches:
        height = patch.get_height()
        if height == 0:
            continue
        ax.text(
            patch.get_x() + patch.get_width() / 2,
            height,
            fmt.format(height),
            ha="center",
            va="bottom",
            fontsize=8,
        )


def _style_axis(ax: plt.Axes, title: str, ylabel: str = "") -> None:
    ax.set_title(title, fontsize=12, fontweight="bold")
    if ylabel:
        ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.25)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def _short_arch(name: str) -> str:
    if name == "llm_unique":
        return "LLM Unique"
    if name == "systeme_multi_agents":
        return "Multi-Agents"
    return name.replace("_", " ").title()


def _draw_boxes(path: Path, title: str, boxes: list[tuple[float, float, str]], arrows: list[tuple[int, int]], outputs: list[Path]) -> None:
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_title(title, fontsize=16, fontweight="bold", pad=18)
    for idx, (x, y, text) in enumerate(boxes):
        ax.text(
            x,
            y,
            text,
            ha="center",
            va="center",
            fontsize=10,
            bbox={
                "boxstyle": "round,pad=0.55",
                "facecolor": "#eef2ff" if idx % 2 == 0 else "#ecfeff",
                "edgecolor": "#334155",
                "linewidth": 1.2,
            },
        )
    for src, dst in arrows:
        x1, y1, _ = boxes[src]
        x2, y2, _ = boxes[dst]
        ax.annotate(
            "",
            xy=(x2, y2),
            xytext=(x1, y1),
            arrowprops={"arrowstyle": "->", "lw": 1.5, "color": COLORS["slate"], "shrinkA": 28, "shrinkB": 28},
        )
    _save(fig, path, outputs)


def chart_architecture_overview(charts_dir: Path, outputs: list[Path]) -> None:
    boxes = [
        (0.12, 0.72, "Tickets IT\nCSV / probes"),
        (0.32, 0.72, "LLM Unique\nzero-shot"),
        (0.32, 0.38, "Systeme\nMulti-Agents"),
        (0.55, 0.38, "Outils\nKB / RAG / statut"),
        (0.74, 0.38, "ChromaDB\n+ JSON KB"),
        (0.56, 0.72, "Juge LLM\nCopilot proxy"),
        (0.82, 0.72, "Scores\nqualite / securite"),
        (0.82, 0.18, "Rapport\nJSON + PNG"),
    ]
    arrows = [(0, 1), (0, 2), (2, 3), (3, 4), (1, 5), (2, 5), (5, 6), (6, 7)]
    _draw_boxes(charts_dir / "architecture_overview.png", "Architecture BibOps", boxes, arrows, outputs)


def chart_react_loop(charts_dir: Path, outputs: list[Path]) -> None:
    boxes = [
        (0.15, 0.55, "Ticket\nutilisateur"),
        (0.35, 0.75, "LLM\nAgentDecision"),
        (0.58, 0.75, "Choix outil\nou final"),
        (0.78, 0.55, "Execution outil\navec timeout"),
        (0.58, 0.32, "Memoire courte\ntrace"),
        (0.35, 0.32, "Reponse finale\nstructuree"),
    ]
    arrows = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 1), (2, 5)]
    _draw_boxes(charts_dir / "react_loop.png", "Boucle ReAct BibOps", boxes, arrows, outputs)


def chart_racing_flux(charts_dir: Path, outputs: list[Path]) -> None:
    boxes = [
        (0.12, 0.68, "RaceEngine\ntelemetrie"),
        (0.34, 0.68, "Hub FastAPI\nSSE broadcast"),
        (0.58, 0.82, "Team A\nzero-shot"),
        (0.58, 0.58, "Team B\nReAct"),
        (0.58, 0.34, "Team C\nvalidated"),
        (0.82, 0.58, "Decisions\nPIT / STAY"),
        (0.34, 0.22, "RAG service\nMichelin docs"),
    ]
    arrows = [(0, 1), (1, 2), (1, 3), (1, 4), (2, 5), (3, 5), (4, 5), (3, 6), (4, 6)]
    _draw_boxes(charts_dir / "racing_flux.png", "Flux Racing Arena", boxes, arrows, outputs)


def chart_comparison(benchmark_dir: Path, charts_dir: Path, outputs: list[Path], warnings: list[str]) -> None:
    path = benchmark_dir / "comparison_results.json"
    data = _load_json(path)
    if not isinstance(data, dict):
        _missing(path, warnings)
        return
    summary = data.get("summary", {})
    composite = data.get("composite", {}).get("architectures", {})
    arches = ["llm_unique", "systeme_multi_agents"]
    labels = [_short_arch(item) for item in arches]

    quality = [_float(summary.get(arch, {}).get("score_moyen")) for arch in arches]
    security = [_float(data.get("security", {}).get(arch, {}).get("security_score_moyen")) for arch in arches]
    composite_scores = [_float(composite.get(arch, {}).get("composite_score")) for arch in arches]
    latency = [_float(summary.get(arch, {}).get("latence_totale_s")) for arch in arches]
    cost = [_float(summary.get(arch, {}).get("cout_usd")) for arch in arches]
    tokens = [_float(summary.get(arch, {}).get("total_tokens")) for arch in arches]

    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    axes[0, 0].bar(labels, quality, color=[COLORS["blue"], COLORS["green"]])
    axes[0, 0].axhline(7, color=COLORS["red"], linestyle="--", linewidth=1, label="gate qualite")
    axes[0, 0].legend()
    _style_axis(axes[0, 0], "Qualite moyenne", "score /10")
    _bar_labels(axes[0, 0])

    x = range(len(labels))
    axes[0, 1].bar([i - 0.18 for i in x], security, width=0.36, color=COLORS["cyan"], label="securite /10")
    axes[0, 1].bar([i + 0.18 for i in x], composite_scores, width=0.36, color=COLORS["purple"], label="composite /100")
    axes[0, 1].set_xticks(list(x), labels)
    axes[0, 1].legend()
    _style_axis(axes[0, 1], "Securite et score composite")

    axes[1, 0].bar(labels, latency, color=[COLORS["orange"], COLORS["green"]])
    _style_axis(axes[1, 0], "Latence totale", "secondes")
    _bar_labels(axes[1, 0])

    ax_tokens = axes[1, 1]
    ax_cost = ax_tokens.twinx()
    ax_tokens.bar([i - 0.18 for i in x], tokens, width=0.36, color=COLORS["blue"], label="tokens")
    ax_cost.bar([i + 0.18 for i in x], cost, width=0.36, color=COLORS["red"], label="cout")
    ax_tokens.set_xticks(list(x), labels)
    ax_tokens.set_ylabel("tokens")
    ax_cost.set_ylabel("USD")
    ax_tokens.set_title("Tokens et cout estime", fontsize=12, fontweight="bold")
    ax_tokens.grid(axis="y", alpha=0.25)
    lines, line_labels = ax_tokens.get_legend_handles_labels()
    lines2, line_labels2 = ax_cost.get_legend_handles_labels()
    ax_tokens.legend(lines + lines2, line_labels + line_labels2, loc="upper right")

    fig.suptitle("Comparaison LLM Unique vs Systeme Multi-Agents", fontsize=15, fontweight="bold")
    _save(fig, charts_dir / "comparaison_architectures.png", outputs)

    fig, axes = plt.subplots(2, 2, figsize=(13, 8))
    metrics = [
        ("Score qualite", quality, "score /10"),
        ("Latence", latency, "secondes"),
        ("Cout", cost, "USD"),
        ("Tokens", tokens, "tokens"),
    ]
    for ax, (title, values, ylabel) in zip(axes.flat, metrics, strict=False):
        ax.bar(labels, values, color=[COLORS["blue"], COLORS["green"]])
        _style_axis(ax, title, ylabel)
        _bar_labels(ax)
    fig.suptitle("Synthese du coeur de benchmark", fontsize=15, fontweight="bold")
    _save(fig, charts_dir / "core_benchmark.png", outputs)


def chart_domain_summary(benchmark_dir: Path, charts_dir: Path, outputs: list[Path], warnings: list[str]) -> None:
    path = benchmark_dir / "comparison_results.json"
    data = _load_json(path)
    if not isinstance(data, dict):
        _missing(path, warnings)
        return
    domain_summary = data.get("domain_summary", {})
    if not isinstance(domain_summary, dict) or not domain_summary:
        return

    rows = list(domain_summary.values())
    labels = [str(row.get("label", "domaine")) for row in rows]
    zero_shot = [_float(row.get("llm_unique_score_moyen")) for row in rows]
    agents = [_float(row.get("systeme_multi_agents_score_moyen")) for row in rows]
    tool_rates = [_float(row.get("agent_tool_use_rate")) * 100 for row in rows]
    fallbacks = [_float(row.get("agent_fallback_count")) for row in rows]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.2))
    x = range(len(labels))
    width = 0.38
    axes[0].bar([i - width / 2 for i in x], zero_shot, width=width, label="LLM Unique", color=COLORS["blue"])
    axes[0].bar([i + width / 2 for i in x], agents, width=width, label="Multi-Agents", color=COLORS["green"])
    axes[0].axhline(7, color=COLORS["red"], linestyle="--", linewidth=1, label="gate qualite")
    axes[0].set_xticks(list(x), labels)
    axes[0].tick_params(axis="x", rotation=20)
    axes[0].legend()
    axes[0].set_ylim(0, 10)
    _style_axis(axes[0], "Qualite moyenne par domaine", "score /10")

    axes[1].bar([i - width / 2 for i in x], tool_rates, width=width, label="tickets avec outil (%)", color=COLORS["purple"])
    axes[1].bar([i + width / 2 for i in x], fallbacks, width=width, label="fallbacks agent", color=COLORS["orange"])
    axes[1].set_xticks(list(x), labels)
    axes[1].tick_params(axis="x", rotation=20)
    axes[1].legend()
    _style_axis(axes[1], "Exploitabilite agent par domaine")

    fig.suptitle("Lecture par domaine du benchmark", fontsize=15, fontweight="bold")
    _save(fig, charts_dir / "domain_quality_breakdown.png", outputs)


def chart_benchmark_diagnostics(benchmark_dir: Path, charts_dir: Path, outputs: list[Path], warnings: list[str]) -> None:
    path = benchmark_dir / "comparison_results.json"
    data = _load_json(path)
    if not isinstance(data, dict):
        _missing(path, warnings)
        return
    diagnostics = data.get("diagnostics", {})
    if not isinstance(diagnostics, dict) or not diagnostics:
        return

    llm_unique = diagnostics.get("llm_unique", {})
    agents = diagnostics.get("systeme_multi_agents", {})
    ticket_count = max(1.0, _float(diagnostics.get("ticket_count"), 1.0))
    counts_labels = ["ZS timeouts", "Agent fallback", "Tool tickets", "Repairs"]
    counts_values = [
        _float(llm_unique.get("timeout_count")),
        _float(agents.get("fallback_count")),
        _float(agents.get("tool_ticket_count")),
        _float(agents.get("empty_answer_repair_count")),
    ]
    rate_labels = ["agent wins", "zero-shot wins", "ties", "tool use %"]
    rate_values = [
        (_float(diagnostics.get("agent_wins")) / ticket_count) * 100,
        (_float(diagnostics.get("zero_shot_wins")) / ticket_count) * 100,
        (_float(diagnostics.get("ties")) / ticket_count) * 100,
        _float(agents.get("tool_use_rate")) * 100,
    ]

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    axes[0].bar(counts_labels, counts_values, color=[COLORS["red"], COLORS["orange"], COLORS["purple"], COLORS["gray"]])
    axes[0].tick_params(axis="x", rotation=20)
    _style_axis(axes[0], "Diagnostics runtime", "count")
    _bar_labels(axes[0], "{:.0f}")

    axes[1].bar(rate_labels, rate_values, color=[COLORS["green"], COLORS["blue"], COLORS["gray"], COLORS["purple"]])
    axes[1].set_ylim(0, 105)
    axes[1].tick_params(axis="x", rotation=20)
    _style_axis(axes[1], "Ratios interpretables", "% tickets")
    _bar_labels(axes[1], "{:.1f}")

    fig.suptitle("Pourquoi le benchmark reussit ou echoue", fontsize=15, fontweight="bold")
    _save(fig, charts_dir / "benchmark_diagnostics.png", outputs)


def chart_composite(benchmark_dir: Path, charts_dir: Path, outputs: list[Path], warnings: list[str]) -> None:
    path = benchmark_dir / "comparison_results.json"
    data = _load_json(path)
    if not isinstance(data, dict):
        _missing(path, warnings)
        return
    composite = data.get("composite", {})
    arch_data = composite.get("architectures", {})
    labels = [_short_arch(key) for key in arch_data]
    scores = [_float(value.get("composite_score")) for value in arch_data.values()]
    verdicts = [str(value.get("release_verdict", "")) for value in arch_data.values()]
    colors = [COLORS["green"] if verdict == "PASS" else COLORS["red"] for verdict in verdicts]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(labels, scores, color=colors)
    ax.set_ylim(0, 100)
    _style_axis(ax, "Verdicts composites", "score /100")
    for idx, (score, verdict) in enumerate(zip(scores, verdicts, strict=False)):
        ax.text(idx, score + 2, f"{score:.1f}\n{verdict}", ha="center", va="bottom", fontweight="bold")
    winner = composite.get("winner", "")
    if winner:
        ax.text(0.02, 0.94, f"winner: {_short_arch(winner)}", transform=ax.transAxes, fontsize=11)
    _save(fig, charts_dir / "composite_verdict.png", outputs)

    weights = composite.get("weights", {})
    if weights:
        fig, ax = plt.subplots(figsize=(7, 7))
        ax.pie(
            list(weights.values()),
            labels=[key.title() for key in weights],
            autopct="%1.0f%%",
            startangle=90,
            colors=[COLORS["blue"], COLORS["green"], COLORS["orange"], COLORS["purple"], COLORS["cyan"]],
        )
        ax.set_title("Ponderation du score composite", fontsize=14, fontweight="bold")
        _save(fig, charts_dir / "composite_weights.png", outputs)


def chart_security_inspector(benchmark_dir: Path, charts_dir: Path, outputs: list[Path], warnings: list[str]) -> None:
    path = benchmark_dir / "comparison_results.json"
    data = _load_json(path)
    if not isinstance(data, dict):
        _missing(path, warnings)
        return
    security = data.get("security", {})
    risks = ["pii", "prompt_injection", "secrets", "malicious_urls", "no_refusal", "toxicity"]
    arches = ["llm_unique", "systeme_multi_agents"]

    fig, ax = plt.subplots(figsize=(12, 4.8))
    x = range(len(risks))
    width = 0.38
    for offset, arch, color in [(-width / 2, arches[0], COLORS["blue"]), (width / 2, arches[1], COLORS["green"])]:
        values = [_float(security.get(arch, {}).get("risks_moyens", {}).get(risk)) for risk in risks]
        ax.bar([i + offset for i in x], values, width=width, label=_short_arch(arch), color=color)
    ax.set_xticks(list(x), [risk.replace("_", "\n") for risk in risks])
    ax.set_ylim(0, 1)
    ax.legend()
    _style_axis(ax, "Inspecteur securite - risques moyens", "risque moyen")
    _save(fig, charts_dir / "security_inspector_demo.png", outputs)


def _mcp_series(payload: Any) -> tuple[list[str], list[float], list[float]]:
    rows = _listify(payload)
    labels = [str(row.get("id_ticket", idx + 1)) for idx, row in enumerate(rows)]
    scores = [_float(row.get("scores", {}).get("score_final")) for row in rows]
    latency = [_float(row.get("temps_reponse_s")) for row in rows]
    return labels, scores, latency


def chart_mcp(benchmark_dir: Path, charts_dir: Path, outputs: list[Path], warnings: list[str]) -> None:
    direct_path = benchmark_dir / "benchmark_mcp.json"
    tools_path = benchmark_dir / "benchmark_mcp_tools.json"
    direct = _load_json(direct_path)
    tools = _load_json(tools_path)
    if not isinstance(direct, list) and not isinstance(tools, list):
        _missing(direct_path, warnings)
        _missing(tools_path, warnings)
        return

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8))
    for ax, payload, title, color in [
        (axes[0], direct, "MCP direct", COLORS["blue"]),
        (axes[1], tools, "MCP outils + pertinence", COLORS["green"]),
    ]:
        labels, scores, _ = _mcp_series(payload)
        ax.bar(labels, scores, color=color)
        ax.set_ylim(0, 10.5)
        _style_axis(ax, title, "score /10")
        _bar_labels(ax)
        ax.tick_params(axis="x", rotation=35)

    rows = []
    names = []
    for name, payload in [("direct", direct), ("tools", tools)]:
        labels, scores, latency = _mcp_series(payload)
        if labels:
            rows.append([sum(scores) / len(scores), sum(latency) / len(latency)])
            names.append(name)
    x = range(len(names))
    axes[2].bar([i - 0.18 for i in x], [row[0] for row in rows], width=0.36, label="score", color=COLORS["purple"])
    axes[2].bar([i + 0.18 for i in x], [row[1] for row in rows], width=0.36, label="latence", color=COLORS["orange"])
    axes[2].set_xticks(list(x), names)
    axes[2].legend()
    _style_axis(axes[2], "Moyennes")
    fig.suptitle("Benchmark MCP", fontsize=15, fontweight="bold")
    _save(fig, charts_dir / "mcp_benchmark.png", outputs)


def _score_payload(path: Path) -> tuple[list[str], list[float], list[float]]:
    data = _load_json(path)
    if not isinstance(data, dict):
        return [], [], []
    scores = data.get("scores", {})
    labels = list(scores.keys())
    values = [_float(value) for value in scores.values()]
    pct = data.get("pourcentages", {})
    percentages = [_float(pct.get(label)) for label in labels]
    return labels, values, percentages


def chart_ab_tests(benchmark_dir: Path, charts_dir: Path, outputs: list[Path], warnings: list[str]) -> None:
    path = benchmark_dir / "ab_llm_resultat.json"
    labels, values, percentages = _score_payload(path)
    if not labels:
        _missing(path, warnings)
        return
    stmt_labels, stmt_values, stmt_pct = _score_payload(benchmark_dir / "ab_llm_statements_result.json")

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    axes[0].bar(labels, values, color=[COLORS["blue"], COLORS["green"], COLORS["orange"]][: len(labels)])
    _style_axis(axes[0], "A/B LLM - votes", "votes")
    _bar_labels(axes[0], "{:.0f}")
    for idx, pct in enumerate(percentages):
        axes[0].text(idx, values[idx] * 0.5 if values[idx] else 0.05, f"{pct:.1f}%", ha="center", color="white", fontweight="bold")

    if stmt_labels:
        axes[1].bar(stmt_labels, stmt_values, color=[COLORS["purple"], COLORS["cyan"], COLORS["orange"]][: len(stmt_labels)])
        _style_axis(axes[1], "Statements - votes", "votes")
        _bar_labels(axes[1], "{:.0f}")
        for idx, pct in enumerate(stmt_pct):
            axes[1].text(idx, stmt_values[idx] * 0.5 if stmt_values[idx] else 0.05, f"{pct:.1f}%", ha="center", color="white", fontweight="bold")
    else:
        axes[1].axis("off")
    fig.suptitle("Tests A/B", fontsize=15, fontweight="bold")
    _save(fig, charts_dir / "ab_test_llm.png", outputs)


def chart_position_bias(benchmark_dir: Path, charts_dir: Path, outputs: list[Path], warnings: list[str]) -> None:
    tickets_path = benchmark_dir / "position_bias_resultat.json"
    tickets = _load_json(tickets_path)
    statements = _load_json(benchmark_dir / "position_bias_statements_result.json")
    if not isinstance(tickets, dict):
        _missing(tickets_path, warnings)
        return
    summary = tickets.get("summary", {})
    values = [_float(summary.get("picks_A_position")), _float(summary.get("picks_B_position"))]
    pvalue = _float(summary.get("binomial_test_two_sided_pvalue"))
    stmt_summary = statements.get("summary", {}) if isinstance(statements, dict) else {}

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    axes[0].bar(["Position A", "Position B"], values, color=[COLORS["blue"], COLORS["green"]])
    _style_axis(axes[0], f"Tickets IT - p={pvalue:.3f}", "jugements")
    _bar_labels(axes[0], "{:.0f}")

    stmt_values = [_float(stmt_summary.get("picks_A")), _float(stmt_summary.get("total")) - _float(stmt_summary.get("picks_A"))]
    axes[1].bar(["Position A", "Position B"], stmt_values, color=[COLORS["purple"], COLORS["cyan"]])
    _style_axis(axes[1], f"Statements - p={_float(stmt_summary.get('binomial_p')):.3f}", "jugements")
    _bar_labels(axes[1], "{:.0f}")
    fig.suptitle("Biais de position du juge", fontsize=15, fontweight="bold")
    _save(fig, charts_dir / "position_bias.png", outputs)


def _historical_rows(path: Path) -> list[dict[str, Any]]:
    data = _load_json(path)
    if not isinstance(data, dict):
        return []
    return _listify(data.get("tickets_evalues"))


def chart_historical_scores(benchmark_dir: Path, charts_dir: Path, outputs: list[Path], warnings: list[str]) -> None:
    path = benchmark_dir / "tickets_evalues_scores.json"
    rows = _historical_rows(path)
    if not rows:
        _missing(path, warnings)
        return
    by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_model[str(row.get("modele", "unknown"))].append(row)
    labels = list(by_model)
    means = [sum(_float(row.get("score_final")) for row in by_model[label]) / len(by_model[label]) for label in labels]

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(labels, means, color=[COLORS["blue"], COLORS["green"], COLORS["orange"], COLORS["purple"]][: len(labels)])
    ax.set_ylim(0, 10)
    _style_axis(ax, "Score moyen par modele", "score /10")
    _bar_labels(ax)
    ax.tick_params(axis="x", rotation=20)
    _save(fig, charts_dir / "graphique_1_score_par_modele.png", outputs)

    fig, ax = plt.subplots(figsize=(10, 5))
    for label, model_rows in by_model.items():
        latencies = [_float(row.get("donnees_brutes", {}).get("temps_reponse_s")) for row in model_rows]
        scores = [_float(row.get("score_final")) for row in model_rows]
        ax.scatter(latencies, scores, s=70, label=label)
    ax.set_xlabel("latence (s)")
    ax.set_ylabel("score /10")
    ax.set_ylim(0, 10)
    ax.legend()
    _style_axis(ax, "Latence vs score")
    _save(fig, charts_dir / "graphique_2_latence_vs_score.png", outputs)

    success = []
    for label in labels:
        model_rows = by_model[label]
        ok = sum(1 for row in model_rows if not row.get("donnees_brutes", {}).get("reponse_erreur", False))
        success.append((ok / len(model_rows)) * 100)
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(labels, success, color=[COLORS["green"], COLORS["blue"], COLORS["orange"], COLORS["purple"]][: len(labels)])
    ax.set_ylim(0, 105)
    _style_axis(ax, "Taux de reussite par modele", "% sans erreur")
    _bar_labels(ax, "{:.1f}")
    ax.tick_params(axis="x", rotation=20)
    _save(fig, charts_dir / "graphique_3_taux_reussite_outils.png", outputs)


def chart_racing(benchmark_dir: Path, charts_dir: Path, outputs: list[Path], warnings: list[str]) -> None:
    path = benchmark_dir / "security_race_report.json"
    data = _load_json(path)
    if not isinstance(data, dict):
        _missing(path, warnings)
        return
    metrics = data.get("security_metrics", {})
    llm_metrics = data.get("llm_professor_metrics", {})
    teams = list(metrics)

    fig, axes = plt.subplots(2, 2, figsize=(13, 8))
    axes[0, 0].bar(teams, [_float(metrics[t].get("attacks_received")) for t in teams], color=COLORS["orange"])
    _style_axis(axes[0, 0], "Attaques recues", "count")
    axes[0, 0].tick_params(axis="x", rotation=20)

    axes[0, 1].bar(teams, [_float(metrics[t].get("injection_execution_rate")) * 100 for t in teams], color=COLORS["red"])
    _style_axis(axes[0, 1], "Taux injection executee", "%")
    axes[0, 1].tick_params(axis="x", rotation=20)

    axes[1, 0].bar(teams, [_float(metrics[t].get("leakage_rate")) * 100 for t in teams], color=COLORS["purple"])
    _style_axis(axes[1, 0], "Taux fuite strategie", "%")
    axes[1, 0].tick_params(axis="x", rotation=20)

    llm_teams = list(llm_metrics)
    axes[1, 1].bar(llm_teams, [_float(llm_metrics[t].get("greenops", {}).get("gCO2e")) for t in llm_teams], color=COLORS["green"])
    _style_axis(axes[1, 1], "GreenOps par equipe", "gCO2e")
    axes[1, 1].tick_params(axis="x", rotation=20)
    fig.suptitle("Racing Arena adversariale", fontsize=15, fontweight="bold")
    _save(fig, charts_dir / "racing_arena.png", outputs)

    fig, ax = plt.subplots(figsize=(12, 5))
    x = range(len(teams))
    width = 0.25
    ax.bar([i - width for i in x], [_float(metrics[t].get("injection_execution_rate")) * 100 for t in teams], width=width, label="injection", color=COLORS["red"])
    ax.bar(list(x), [_float(metrics[t].get("leakage_rate")) * 100 for t in teams], width=width, label="fuite", color=COLORS["purple"])
    ax.bar([i + width for i in x], [_float(metrics[t].get("detection_rate")) * 100 for t in teams], width=width, label="detection", color=COLORS["green"])
    ax.set_xticks(list(x), teams)
    ax.tick_params(axis="x", rotation=20)
    ax.legend()
    _style_axis(ax, "Securite Racing par equipe", "%")
    _save(fig, charts_dir / "racing_security_report.png", outputs)


def chart_a2a(benchmark_dir: Path, charts_dir: Path, outputs: list[Path], warnings: list[str]) -> None:
    path = benchmark_dir / "a2a_agents_results.json"
    data = _load_json(path)
    if not isinstance(data, dict):
        _missing(path, warnings)
        return
    rows = [row for row in _listify(data.get("summary")) if _float(row.get("avg_quality")) > 0 or _float(row.get("avg_task_score")) > 0]
    if not rows:
        warnings.append(f"no usable A2A rows in: {path}")
        return
    labels = [str(row.get("agent")) for row in rows]
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.8))
    axes[0].bar(labels, [_float(row.get("avg_quality")) for row in rows], color=COLORS["blue"])
    _style_axis(axes[0], "A2A qualite", "score /10")
    axes[1].bar(labels, [_float(row.get("avg_task_score")) for row in rows], color=COLORS["green"])
    _style_axis(axes[1], "A2A task score", "score /10")
    axes[2].bar(labels, [_float(row.get("avg_latency_s")) for row in rows], color=COLORS["orange"])
    _style_axis(axes[2], "A2A latence", "secondes")
    for ax in axes:
        ax.tick_params(axis="x", rotation=45)
    fig.suptitle("Benchmark agents A2A", fontsize=15, fontweight="bold")
    _save(fig, charts_dir / "a2a_agents.png", outputs)


def chart_kaggle(benchmark_dir: Path, charts_dir: Path, outputs: list[Path], warnings: list[str]) -> None:
    latest = _latest_json(benchmark_dir / "kaggle", "local_kaggle_exam_report_*.json")
    if latest is None:
        _missing(benchmark_dir / "kaggle/local_kaggle_exam_report_*.json", warnings)
        return
    data = _load_json(latest)
    if not isinstance(data, dict):
        _missing(latest, warnings)
        return
    summary = data.get("summary", {})
    results = _listify(data.get("results"))
    correct = sum(1 for row in results if row.get("judge", {}).get("correct") is True or row.get("correct") is True)
    incorrect = len(results) - correct
    fmt_ok = sum(1 for row in results if row.get("judge", {}).get("format_ok") is True)
    safety_ok = sum(1 for row in results if row.get("judge", {}).get("safety_ok") is True)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    axes[0].bar(["score", "reste"], [_float(summary.get("score")), max(0, _float(summary.get("max_score")) - _float(summary.get("score")))], color=[COLORS["green"], COLORS["gray"]])
    _style_axis(axes[0], f"Kaggle local - {latest.name}", "points")
    axes[1].bar(["correct", "incorrect", "format_ok", "safety_ok"], [correct, incorrect, fmt_ok, safety_ok], color=[COLORS["green"], COLORS["red"], COLORS["blue"], COLORS["purple"]])
    _style_axis(axes[1], "Questions", "count")
    _save(fig, charts_dir / "kaggle_exam.png", outputs)


def chart_coverage(coverage_json: Path, eval_bank_dir: Path, charts_dir: Path, outputs: list[Path], warnings: list[str]) -> None:
    data = _load_json(coverage_json)
    if not isinstance(data, dict):
        _missing(coverage_json, warnings)
        return
    totals = data.get("totals", {})
    quality = _load_json(eval_bank_dir / "quality_run.json") or {}
    security = _load_json(eval_bank_dir / "security_run.json") or {}
    q_summary = quality.get("summary", {}) if isinstance(quality, dict) else {}
    s_summary = security.get("summary", {}) if isinstance(security, dict) else {}

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    axes[0].bar(
        ["lines", "branches"],
        [_float(totals.get("percent_covered")), _float(totals.get("percent_branches_covered"))],
        color=[COLORS["blue"], COLORS["purple"]],
    )
    axes[0].set_ylim(0, 100)
    _style_axis(axes[0], "Couverture tests", "%")
    _bar_labels(axes[0])

    labels = ["quality total", "quality failed", "security total", "security failed"]
    values = [
        _float(q_summary.get("total")),
        _float(q_summary.get("failed")),
        _float(s_summary.get("total")),
        _float(s_summary.get("failed")),
    ]
    axes[1].bar(labels, values, color=[COLORS["blue"], COLORS["red"], COLORS["green"], COLORS["red"]])
    axes[1].tick_params(axis="x", rotation=25)
    _style_axis(axes[1], "Suites eval_bank", "tests")
    _save(fig, charts_dir / "coverage_summary.png", outputs)


def chart_synthesis(benchmark_dir: Path, charts_dir: Path, coverage_json: Path, outputs: list[Path], warnings: list[str]) -> None:
    comparison = _load_json(benchmark_dir / "comparison_results.json") or {}
    mcp_tools = _load_json(benchmark_dir / "benchmark_mcp_tools.json") or []
    racing = _load_json(benchmark_dir / "security_race_report.json") or {}
    coverage = _load_json(coverage_json) or {}
    position = _load_json(benchmark_dir / "position_bias_resultat.json") or {}

    composite = comparison.get("composite", {}).get("architectures", {}) if isinstance(comparison, dict) else {}
    sma_score = _float(composite.get("systeme_multi_agents", {}).get("composite_score"))
    mcp_score = 0.0
    if isinstance(mcp_tools, list) and mcp_tools:
        mcp_score = sum(_float(row.get("scores", {}).get("score_final")) for row in mcp_tools) / len(mcp_tools)
    team_c = racing.get("security_metrics", {}).get("team_c_validated", {}) if isinstance(racing, dict) else {}
    team_c_resistance = (1 - _float(team_c.get("injection_execution_rate"))) * 100 if team_c else 0.0
    coverage_pct = _float(coverage.get("totals", {}).get("percent_covered")) if isinstance(coverage, dict) else 0.0
    pvalue = _float(position.get("summary", {}).get("binomial_test_two_sided_pvalue")) if isinstance(position, dict) else 0.0

    labels = ["SMA composite", "MCP score", "Team C resistance", "Coverage", "Position p-value"]
    values = [sma_score, mcp_score * 10, team_c_resistance, coverage_pct, pvalue * 100]

    fig, ax = plt.subplots(figsize=(12, 5.5))
    ax.bar(labels, values, color=[COLORS["green"], COLORS["blue"], COLORS["purple"], COLORS["orange"], COLORS["cyan"]])
    ax.set_ylim(0, 105)
    _style_axis(ax, "Synthese finale des benchmarks", "score normalise /100")
    _bar_labels(ax)
    ax.tick_params(axis="x", rotation=20)
    _save(fig, charts_dir / "synthese_finale.png", outputs)


def generate_all_charts(
    *,
    benchmark_dir: Path = DEFAULT_BENCHMARK_DIR,
    charts_dir: Path = DEFAULT_CHARTS_DIR,
    coverage_json: Path = DEFAULT_COVERAGE_JSON,
    eval_bank_dir: Path = DEFAULT_EVAL_BANK_DIR,
    strict: bool = False,
) -> dict[str, Any]:
    outputs: list[Path] = []
    warnings: list[str] = []
    charts_dir.mkdir(parents=True, exist_ok=True)

    chart_architecture_overview(charts_dir, outputs)
    chart_react_loop(charts_dir, outputs)
    chart_racing_flux(charts_dir, outputs)
    chart_comparison(benchmark_dir, charts_dir, outputs, warnings)
    chart_domain_summary(benchmark_dir, charts_dir, outputs, warnings)
    chart_benchmark_diagnostics(benchmark_dir, charts_dir, outputs, warnings)
    chart_composite(benchmark_dir, charts_dir, outputs, warnings)
    chart_security_inspector(benchmark_dir, charts_dir, outputs, warnings)
    chart_mcp(benchmark_dir, charts_dir, outputs, warnings)
    chart_ab_tests(benchmark_dir, charts_dir, outputs, warnings)
    chart_position_bias(benchmark_dir, charts_dir, outputs, warnings)
    chart_historical_scores(benchmark_dir, charts_dir, outputs, warnings)
    chart_racing(benchmark_dir, charts_dir, outputs, warnings)
    chart_a2a(benchmark_dir, charts_dir, outputs, warnings)
    chart_kaggle(benchmark_dir, charts_dir, outputs, warnings)
    chart_coverage(coverage_json, eval_bank_dir, charts_dir, outputs, warnings)
    chart_synthesis(benchmark_dir, charts_dir, coverage_json, outputs, warnings)

    if strict and warnings:
        raise FileNotFoundError("\n".join(warnings))
    return {
        "charts_dir": str(charts_dir),
        "generated": [str(path) for path in outputs],
        "warnings": warnings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate BibOps report charts from benchmark JSON files.")
    parser.add_argument("--benchmark-dir", type=Path, default=DEFAULT_BENCHMARK_DIR)
    parser.add_argument("--charts-dir", type=Path, default=DEFAULT_CHARTS_DIR)
    parser.add_argument("--coverage-json", type=Path, default=DEFAULT_COVERAGE_JSON)
    parser.add_argument("--eval-bank-dir", type=Path, default=DEFAULT_EVAL_BANK_DIR)
    parser.add_argument("--strict", action="store_true", help="Fail if an expected source JSON is missing.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable generation summary.")
    args = parser.parse_args(argv)

    result = generate_all_charts(
        benchmark_dir=args.benchmark_dir,
        charts_dir=args.charts_dir,
        coverage_json=args.coverage_json,
        eval_bank_dir=args.eval_bank_dir,
        strict=args.strict,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"[OK] Generated {len(result['generated'])} chart(s) in {result['charts_dir']}")
        for chart in result["generated"]:
            print(f"  - {chart}")
        for warning in result["warnings"]:
            print(f"[WARN] {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
