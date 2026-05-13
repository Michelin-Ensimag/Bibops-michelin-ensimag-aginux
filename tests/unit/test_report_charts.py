from __future__ import annotations

import json

import pytest


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_generate_charts_from_minimal_comparison_payload(tmp_path):
    from src.bibops.reporting.charts import generate_all_charts

    benchmark_dir = tmp_path / "benchmark"
    charts_dir = benchmark_dir / "charts"
    _write_json(
        benchmark_dir / "comparison_results.json",
        {
            "summary": {
                "llm_unique": {
                    "score_moyen": 4,
                    "latence_totale_s": 10,
                    "cout_usd": 0.01,
                    "total_tokens": 100,
                },
                "systeme_multi_agents": {
                    "score_moyen": 7,
                    "latence_totale_s": 6,
                    "cout_usd": 0.005,
                    "total_tokens": 50,
                },
            },
            "security": {
                "llm_unique": {"security_score_moyen": 9, "risks_moyens": {}},
                "systeme_multi_agents": {"security_score_moyen": 10, "risks_moyens": {}},
            },
            "composite": {
                "weights": {"quality": 0.4, "security": 0.35, "finops": 0.1, "latency": 0.1, "greenops": 0.05},
                "architectures": {
                    "llm_unique": {"composite_score": 62, "release_verdict": "FAIL"},
                    "systeme_multi_agents": {"composite_score": 84, "release_verdict": "PASS"},
                },
                "winner": "systeme_multi_agents",
            },
            "domain_summary": {
                "it": {
                    "label": "IT",
                    "ticket_count": 2,
                    "llm_unique_score_moyen": 4,
                    "systeme_multi_agents_score_moyen": 7,
                    "agent_tool_use_rate": 0.5,
                    "agent_fallback_count": 1,
                }
            },
            "diagnostics": {
                "ticket_count": 2,
                "agent_wins": 1,
                "zero_shot_wins": 1,
                "ties": 0,
                "llm_unique": {"timeout_count": 1},
                "systeme_multi_agents": {
                    "fallback_count": 1,
                    "tool_ticket_count": 1,
                    "empty_answer_repair_count": 0,
                    "tool_use_rate": 0.5,
                },
            },
        },
    )

    result = generate_all_charts(
        benchmark_dir=benchmark_dir,
        charts_dir=charts_dir,
        coverage_json=tmp_path / "coverage.json",
        eval_bank_dir=tmp_path / "eval_bank",
    )

    assert charts_dir.joinpath("comparaison_architectures.png").exists()
    assert charts_dir.joinpath("composite_verdict.png").exists()
    assert charts_dir.joinpath("architecture_overview.png").exists()
    assert charts_dir.joinpath("domain_quality_breakdown.png").exists()
    assert charts_dir.joinpath("benchmark_diagnostics.png").exists()
    assert any("missing source" in warning for warning in result["warnings"])


def test_generate_charts_strict_fails_when_sources_are_missing(tmp_path):
    from src.bibops.reporting.charts import generate_all_charts

    with pytest.raises(FileNotFoundError):
        generate_all_charts(
            benchmark_dir=tmp_path / "benchmark",
            charts_dir=tmp_path / "charts",
            coverage_json=tmp_path / "coverage.json",
            eval_bank_dir=tmp_path / "eval_bank",
            strict=True,
        )
