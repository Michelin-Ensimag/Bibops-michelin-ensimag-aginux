#!/usr/bin/env python3
"""Validate benchmark output schema and critical fields."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REQUIRED_ARCHES = ("llm_unique", "systeme_multi_agents")
REQUIRED_RISKS = ("pii", "prompt_injection", "secrets", "malicious_urls", "no_refusal", "toxicity")
REQUIRED_TOP_KEYS = (
    "schema_version",
    "generated_at_utc",
    "config",
    "summary",
    "quality",
    "security",
    "composite",
    "details",
)

DETAIL_ARCH_KEYS = {
    "llm_unique": "llm_unique",
    "systeme_multi_agents": "multi_agents",
}


def _expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def _validate_arch_metrics(payload: dict[str, Any], errors: list[str]) -> None:
    summary = payload.get("summary", {})
    quality = payload.get("quality", {})
    security = payload.get("security", {})
    composite = payload.get("composite", {})
    composite_arches = composite.get("architectures", {})

    for arch in REQUIRED_ARCHES:
        arch_summary = summary.get(arch, {})
        arch_quality = quality.get(arch, {})
        arch_security = security.get(arch, {})
        arch_composite = composite_arches.get(arch, {})

        _expect(isinstance(arch_summary, dict), f"summary.{arch} missing", errors)
        _expect(isinstance(arch_quality, dict), f"quality.{arch} missing", errors)
        _expect(isinstance(arch_security, dict), f"security.{arch} missing", errors)
        _expect(isinstance(arch_composite, dict), f"composite.architectures.{arch} missing", errors)

        _expect("score_moyen" in arch_summary, f"summary.{arch}.score_moyen missing", errors)
        _expect("latence_totale_s" in arch_summary, f"summary.{arch}.latence_totale_s missing", errors)
        _expect("cout_usd" in arch_summary, f"summary.{arch}.cout_usd missing", errors)
        _expect("empreinte_gco2e" in arch_summary, f"summary.{arch}.empreinte_gco2e missing", errors)

        _expect("score_moyen" in arch_quality, f"quality.{arch}.score_moyen missing", errors)
        _expect("nb_reponses_notees" in arch_quality, f"quality.{arch}.nb_reponses_notees missing", errors)

        _expect(
            "security_score_moyen" in arch_security,
            f"security.{arch}.security_score_moyen missing",
            errors,
        )
        _expect("blocked_count" in arch_security, f"security.{arch}.blocked_count missing", errors)
        _expect("error_count" in arch_security, f"security.{arch}.error_count missing", errors)
        risks = arch_security.get("risks_moyens", {})
        _expect(isinstance(risks, dict), f"security.{arch}.risks_moyens missing", errors)
        for risk_key in REQUIRED_RISKS:
            _expect(risk_key in risks, f"security.{arch}.risks_moyens.{risk_key} missing", errors)

        _expect("composite_score" in arch_composite, f"composite.architectures.{arch}.composite_score missing", errors)
        _expect("release_verdict" in arch_composite, f"composite.architectures.{arch}.release_verdict missing", errors)
        verdict = str(arch_composite.get("release_verdict", ""))
        _expect(verdict in {"PASS", "FAIL"}, f"composite.architectures.{arch}.release_verdict invalid", errors)
        _expect("component_scores" in arch_composite, f"composite.architectures.{arch}.component_scores missing", errors)
        _expect("reasons" in arch_composite, f"composite.architectures.{arch}.reasons missing", errors)


def validate_payload(payload: dict[str, Any]) -> list[str]:
    """Validate payload and return a list of errors."""
    errors: list[str] = []

    for key in REQUIRED_TOP_KEYS:
        _expect(key in payload, f"Top-level key missing: {key}", errors)

    config = payload.get("config", {})
    _expect(isinstance(config, dict), "config must be object", errors)
    enabled = config.get("enabled_evaluators", [])
    _expect(isinstance(enabled, list), "config.enabled_evaluators must be list", errors)
    _expect("quality" in enabled, "enabled_evaluators must contain quality", errors)
    _expect("security" in enabled, "enabled_evaluators must contain security", errors)

    composite = payload.get("composite", {})
    _expect(isinstance(composite, dict), "composite must be object", errors)
    _expect("policy_version" in composite, "composite.policy_version missing", errors)
    _expect("winner" in composite, "composite.winner missing", errors)
    _expect("architectures" in composite, "composite.architectures missing", errors)

    details = payload.get("details", [])
    _expect(isinstance(details, list), "details must be list", errors)
    if details:
        first = details[0]
        _expect(isinstance(first, dict), "details[0] must be object", errors)
        for arch in REQUIRED_ARCHES:
            details_key = DETAIL_ARCH_KEYS.get(arch, arch)
            item = first.get(details_key, {})
            _expect(isinstance(item, dict), f"details[0].{details_key} missing", errors)
            _expect("quality" in item, f"details[0].{details_key}.quality missing", errors)
            _expect("security" in item, f"details[0].{details_key}.security missing", errors)

    _validate_arch_metrics(payload, errors)
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate benchmark output JSON schema.")
    parser.add_argument(
        "--input",
        required=True,
        help="Path to comparison_results.json",
    )
    args = parser.parse_args()

    path = Path(args.input)
    if not path.exists():
        raise SystemExit(f"[FAIL] File not found: {path}")

    with open(path, encoding="utf-8") as f:
        payload = json.load(f)

    errors = validate_payload(payload)
    if errors:
        print("[FAIL] Benchmark output invalid:")
        for err in errors:
            print(f" - {err}")
        raise SystemExit(1)

    print("[OK] Benchmark output schema is valid.")


if __name__ == "__main__":
    main()
