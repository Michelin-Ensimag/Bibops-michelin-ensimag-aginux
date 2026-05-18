"""
Benchmark de convergence adversariale  —  ReAct vs Zero-Shot.

Pour chaque ticket d'un dataset (10 tickets IT Michelin + RCA), on lance la boucle
adversariale (`run_adversarial_training`) dans deux configs :

  * mode="react"     -> générateur = maestro (ReAct + 3 outils RAG)
  * mode="zero_shot" -> générateur = un appel LLM direct, sans outil

Même générateur (gpt-4o-mini), même juge (gpt-4o), même nombre d'itérations.

Sortie :
  data/outputs/benchmark/adversarial_convergence.json   (résultats bruts agrégés)
  data/outputs/benchmark/charts/adversarial_convergence.png (graphique)

Lancement :
  bibops bench adversarial
  bibops bench adversarial --max-tickets 3
  PYTHONPATH=. python -m src.bibops.benchmark.adversarial_convergence
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import tempfile
import time
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "bibops-matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.bibops.benchmark.adversarial import (
    AdversarialReport,
    GeneratorMode,
    run_adversarial_training,
)
from src.common.config import BASE_DIR

DATASET_PATH = BASE_DIR / "data" / "inputs" / "benchmark" / "adversarial_tickets.json"
OUTPUT_JSON = BASE_DIR / "data" / "outputs" / "benchmark" / "adversarial_convergence.json"
OUTPUT_CHART = BASE_DIR / "data" / "outputs" / "benchmark" / "charts" / "adversarial_convergence.png"


def _per_iteration_means(reports: list[AdversarialReport], max_iter: int) -> dict[str, list[float]]:
    """Moyenne par index d'itération sur tous les tickets. Si un ticket converge tôt,
    on extrapole la dernière valeur (steady state)."""
    metrics: dict[str, list[float]] = {"faithfulness": [], "relevance": [], "context": [], "average": []}
    for it_idx in range(max_iter):
        cols = {"faithfulness": [], "relevance": [], "context": [], "average": []}
        for rep in reports:
            it = rep.iterations[it_idx] if it_idx < len(rep.iterations) else rep.iterations[-1]
            cols["faithfulness"].append(it.score_faithfulness)
            cols["relevance"].append(it.score_relevance)
            cols["context"].append(it.score_context)
            cols["average"].append(it.score_moyen)
        for key, vals in cols.items():
            metrics[key].append(round(statistics.mean(vals), 2))
    return metrics


_RESPONSE_MAX_CHARS = 800


def _truncate(text: str, limit: int = _RESPONSE_MAX_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def _summarize_report(rep: AdversarialReport, ticket_id: str) -> dict[str, Any]:
    return {
        "ticket_id": ticket_id,
        "ticket_text": rep.ticket,
        "rca_ground_truth": rep.rca_ground_truth,
        "succes": rep.succes,
        "iterations_necessaires": rep.iterations_necessaires,
        "scores_par_iteration": [
            {
                "iter": it.numero,
                "faithfulness": it.score_faithfulness,
                "relevance": it.score_relevance,
                "context": it.score_context,
                "moy": it.score_moyen,
                "reponse_agent": _truncate(it.reponse_agent),
                "feedback": it.feedback,
                "tool_calls": list(it.tool_calls),
            }
            for it in rep.iterations
        ],
    }


def run_benchmark(
    dataset: list[dict[str, str]],
    *,
    generator_model: str,
    generator_provider: str,
    judge_model: str,
    max_iterations: int,
    verbose: bool,
) -> dict[str, Any]:
    modes: list[GeneratorMode] = ["zero_shot", "react"]
    results: dict[str, Any] = {
        "config": {
            "generator_model": generator_model,
            "generator_provider": generator_provider,
            "judge_model": judge_model,
            "max_iterations": max_iterations,
            "tickets_count": len(dataset),
        },
        "modes": {},
    }

    for mode in modes:
        print(f"\n{'='*70}\n  MODE : {mode.upper()}  —  {len(dataset)} tickets\n{'='*70}")
        t_mode_start = time.perf_counter()
        reports: list[AdversarialReport] = []
        for idx, item in enumerate(dataset, start=1):
            print(f"\n[{mode}] Ticket {idx}/{len(dataset)} — {item['id']}")
            reports.append(run_adversarial_training(
                ticket=item["ticket"],
                rca_ground_truth=item["rca"],
                contexte_initial=item["contexte"],
                max_iterations=max_iterations,
                modele_agent=generator_model,
                generator_provider=generator_provider,
                modele_discriminateur=judge_model,
                mode=mode,
                verbose=verbose,
            ))

        results["modes"][mode] = {
            "per_iteration": _per_iteration_means(reports, max_iterations),
            "success_rate": round(sum(1 for r in reports if r.succes) / len(reports), 3) if reports else 0.0,
            "total_cost_usd": round(sum(r.cout_estime_usd for r in reports), 4),
            "wallclock_s": round(time.perf_counter() - t_mode_start, 1),
            "reports": [_summarize_report(rep, dataset[i]["id"]) for i, rep in enumerate(reports)],
        }
    return results


def make_chart(results: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    max_iter = results["config"]["max_iterations"]
    x = list(range(1, max_iter + 1))

    fig, (ax_avg, ax_breakdown) = plt.subplots(1, 2, figsize=(14, 5.5))
    color_react, color_zero = "#2563eb", "#dc2626"

    # Panneau 1 : score moyen RAGAS par itération
    react_avg = results["modes"]["react"]["per_iteration"]["average"]
    zero_avg = results["modes"]["zero_shot"]["per_iteration"]["average"]
    ax_avg.plot(x, react_avg, marker="o", color=color_react, linewidth=2.5, label="ReAct + RAG")
    ax_avg.plot(x, zero_avg, marker="s", color=color_zero, linewidth=2.5, label="Zero-shot")
    ax_avg.axhline(7, color="#16a34a", linestyle="--", alpha=0.6, label="Seuil succès (moy ≥ 7/10)")
    ax_avg.set_xlabel("Itération adversariale", fontsize=11)
    ax_avg.set_ylabel("Score RAGAS moyen (/10)", fontsize=11)
    ax_avg.set_title("Convergence — score moyen par itération", fontsize=12, fontweight="bold")
    ax_avg.set_xticks(x)
    ax_avg.set_ylim(0, 10.5)
    ax_avg.grid(alpha=0.3)
    ax_avg.legend(loc="lower right", fontsize=10)

    # Panneau 2 : décomposition F/R/C à l'itération finale
    metrics = ["faithfulness", "relevance", "context"]
    finals = {
        "react": [results["modes"]["react"]["per_iteration"][m][-1] for m in metrics],
        "zero": [results["modes"]["zero_shot"]["per_iteration"][m][-1] for m in metrics],
    }
    width = 0.35
    xpos = list(range(len(metrics)))
    for offset, key, color, label in (
        (-width / 2, "react", color_react, "ReAct + RAG"),
        (+width / 2, "zero", color_zero, "Zero-shot"),
    ):
        ax_breakdown.bar([p + offset for p in xpos], finals[key], width, color=color, label=label)
        for i, v in enumerate(finals[key]):
            ax_breakdown.text(i + offset, v + 0.15, f"{v:.1f}", ha="center", fontsize=9)
    ax_breakdown.set_xticks(xpos)
    ax_breakdown.set_xticklabels(["Fidélité", "Pertinence", "Contexte"], fontsize=10)
    ax_breakdown.set_ylabel("Score moyen final (/10)", fontsize=11)
    ax_breakdown.set_title(f"Décomposition à l'itération {max_iter}", fontsize=12, fontweight="bold")
    ax_breakdown.set_ylim(0, 10.5)
    ax_breakdown.grid(axis="y", alpha=0.3)
    ax_breakdown.legend(loc="upper right", fontsize=10)

    # Footer global
    cfg = results["config"]
    sr_react = results["modes"]["react"]["success_rate"] * 100
    sr_zero = results["modes"]["zero_shot"]["success_rate"] * 100
    cost_total = (results["modes"]["react"]["total_cost_usd"]
                  + results["modes"]["zero_shot"]["total_cost_usd"])
    fig.suptitle(
        f"Boucle adversariale RAGAS  —  Générateur {cfg['generator_model']}"
        f" / Juge {cfg['judge_model']}  ({cfg['tickets_count']} tickets)",
        fontsize=13, fontweight="bold", y=1.02,
    )
    fig.text(
        0.5, -0.04,
        f"Taux de succès : ReAct={sr_react:.0f}% | Zero-shot={sr_zero:.0f}%"
        f"   —   Coût total juge : ${cost_total:.4f}",
        ha="center", fontsize=10, color="#475569",
    )

    fig.tight_layout()
    fig.savefig(output, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\n[chart] écrit : {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-tickets", type=int, default=None, help="Limite le nombre de tickets pour un test rapide.")
    parser.add_argument("--max-iter", type=int, default=2, help="Itérations adversariales par ticket (default: 2).")
    parser.add_argument("--generator-model", default="gpt-4o-mini")
    parser.add_argument("--generator-provider", default="copilot", choices=["copilot", "ollama"])
    parser.add_argument("--judge-model", default="gpt-4o")
    parser.add_argument("--quiet", action="store_true", help="Réduit la verbosité de chaque run adversariale.")
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--output-chart", type=Path, default=OUTPUT_CHART)
    args = parser.parse_args()

    with args.dataset.open(encoding="utf-8") as fh:
        dataset = json.load(fh)["tickets"]
    if args.max_tickets is not None:
        dataset = dataset[: args.max_tickets]

    print(f"\n[setup] {len(dataset)} tickets chargés depuis {args.dataset}")
    print(f"[setup] générateur={args.generator_model} ({args.generator_provider})"
          f" / juge={args.judge_model} / max_iter={args.max_iter}")

    t0 = time.perf_counter()
    results = run_benchmark(
        dataset,
        generator_model=args.generator_model,
        generator_provider=args.generator_provider,
        judge_model=args.judge_model,
        max_iterations=args.max_iter,
        verbose=not args.quiet,
    )
    results["wallclock_total_s"] = round(time.perf_counter() - t0, 1)

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    with args.output_json.open("w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=2)
    print(f"\n[json]  écrit : {args.output_json}")

    make_chart(results, args.output_chart)

    print("\n" + "=" * 70 + "\n  RÉSUMÉ FINAL\n" + "=" * 70)
    for mode in ("react", "zero_shot"):
        m = results["modes"][mode]
        print(f"  {mode:<10} succès={m['success_rate']*100:5.1f}%  "
              f"avg_final={m['per_iteration']['average'][-1]:.2f}/10  "
              f"coût=${m['total_cost_usd']:.4f}  "
              f"durée={m['wallclock_s']:.1f}s")


if __name__ == "__main__":
    main()
