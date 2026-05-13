"""
ObserverEngine — passive security observer for the Racing Arena.

Isolated from the WeakProxy: it only records events that the hub explicitly
reports to it. Teams cannot reach it directly; it has no exposed endpoints.

Records:
  - relay attacks (attacker → hub → target team)
  - strategy probes (GET /team/*/strategy)
  - strategy extractions by Team Psi

Produces:
  - data/runtime/racing/observer_log.jsonl   (append-only event log)
  - data/outputs/benchmark/security_race_report.json  (finalized on race end)
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ..shared.security_metrics import (
    AttackEvent,
    TeamSecurityMetrics,
    detect_data_leaked,
    detect_injection_executed,
    detect_self_detection,
)

_LOG_DIR    = Path(__file__).resolve().parents[3] / "data" / "runtime" / "racing"
_REPORT_DIR = Path(__file__).resolve().parents[3] / "data" / "outputs" / "benchmark"


class ObserverEngine:
    """
    Singleton-style observer.  Instantiated once by the hub server at startup.
    All recording is synchronous (no async overhead) so it never blocks FastAPI.
    """

    def __init__(self) -> None:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        self._log_path  = _LOG_DIR / "observer_log.jsonl"
        self._log_file  = open(self._log_path, "w", encoding="utf-8")
        self._metrics:  dict[str, TeamSecurityMetrics] = {}
        self._psi_extractions: list[dict] = []

    # ------------------------------------------------------------------
    # Recording API (called by hub endpoints)
    # ------------------------------------------------------------------

    def record_relay(
        self,
        *,
        attacker: str,
        target: str,
        attack_type: str,
        payload: str,
        response: str,
        lap: int,
    ) -> AttackEvent:
        """Score and record one relay attack attempt."""
        executed = detect_injection_executed(response)
        leaked   = detect_data_leaked(response)
        detected = detect_self_detection(response)

        event = AttackEvent(
            lap=lap,
            attacker=attacker,
            target=target,
            attack_type=attack_type,
            payload=payload,
            response=response,
            injection_executed=executed,
            data_leaked=leaked,
            detected=detected,
        )

        m = self._get_metrics(target)
        m.attacks_received += 1
        if executed:
            m.injections_executed += 1
        if leaked:
            m.strategy_data_leaked += 1
        if detected:
            m.anomalies_self_detected += 1
        m.attack_events.append(event)

        self._write({
            "type":              "relay_attack",
            "lap":               lap,
            "attacker":          attacker,
            "target":            target,
            "attack_type":       attack_type,
            "payload_preview":   payload[:100],
            "response_preview":  response[:200],
            "injection_executed": executed,
            "data_leaked":       leaked,
            "detected":          detected,
        })
        return event

    def record_strategy_probe(self, *, requester: str, target: str, lap: int) -> None:
        self._write({
            "type":      "strategy_probe",
            "lap":       lap,
            "requester": requester,
            "target":    target,
        })

    def record_psi_extraction(self, *, lap: int, target: str, extracted: str) -> None:
        self._psi_extractions.append({
            "lap":      lap,
            "target":   target,
            "extracted": extracted[:300],
        })
        self._write({
            "type":              "psi_extraction",
            "lap":               lap,
            "target":            target,
            "extracted_preview": extracted[:150],
        })

    # ------------------------------------------------------------------
    # Finalization
    # ------------------------------------------------------------------

    def finalize(self, race_summary: dict[str, Any]) -> dict[str, Any]:
        """Generate and persist the final security report.  Call once after race ends."""
        self._log_file.close()

        # Extract race decisions for LLM Professor metrics (remove from summary to keep it clean)
        race_decisions: list[dict] = race_summary.pop("decisions", [])

        report: dict[str, Any] = {
            "generated_at":              datetime.now().isoformat(timespec="seconds"),
            "race_summary":              race_summary,
            "security_metrics":          {tid: m.to_dict() for tid, m in self._metrics.items()},
            "attack_type_effectiveness": self._compute_effectiveness(),
            "llm_professor_metrics":     self._compute_llm_professor_metrics(race_decisions),
            "pseudo_team": {
                "extractions_count":    len(self._psi_extractions),
                "extractions":          self._psi_extractions,
                "race_advantage_gained": len(self._psi_extractions) > 0,
            },
            "audit_log": str(self._log_path),
        }

        _REPORT_DIR.mkdir(parents=True, exist_ok=True)
        report_path = _REPORT_DIR / "security_race_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\n[OBSERVER] Security report → {report_path}")
        return report

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_metrics(self, team_id: str) -> TeamSecurityMetrics:
        if team_id not in self._metrics:
            self._metrics[team_id] = TeamSecurityMetrics(team_id=team_id)
        return self._metrics[team_id]

    def _write(self, payload: dict) -> None:
        payload["timestamp"] = datetime.now().isoformat(timespec="milliseconds")
        self._log_file.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self._log_file.flush()

    def _compute_llm_professor_metrics(self, decisions: list[dict]) -> dict[str, Any]:
        """
        Applies SecurityLLMInspectorAdapter + GreenOps to each team's race decision
        reasoning texts. No LLM judge required — uses deterministic rule-based scoring.
        """
        from src.bibops.evaluation.metrics.greenops import calculate_carbon_footprint
        from src.bibops.evaluation.security_evaluator import SecurityLLMInspectorAdapter

        security = SecurityLLMInspectorAdapter()
        by_team: dict[str, list[dict]] = {}
        for d in decisions:
            tid = d.get("team_id", "unknown")
            by_team.setdefault(tid, []).append(d)

        metrics: dict[str, Any] = {}
        for tid, decs in by_team.items():
            sec_scores: list[float] = []
            total_tokens = 0
            box_count    = sum(1 for d in decs if d.get("action", "").upper() == "BOX BOX")

            for d in decs:
                reasoning = str(d.get("reasoning") or "")
                if reasoning:
                    result = security.evaluate({"ticket_text": "", "answer_text": reasoning})
                    sec_scores.append(result["security_score"])
                    total_tokens += len(reasoning.split())

            avg_security = round(sum(sec_scores) / len(sec_scores), 2) if sec_scores else None
            greenops     = calculate_carbon_footprint(total_tokens, "cpu") if total_tokens else {}

            metrics[tid] = {
                "decisions_count":              len(decs),
                "box_box_count":                box_count,
                "avg_security_score_0_10":      avg_security,
                "total_reasoning_tokens_approx": total_tokens,
                "greenops":                     greenops,
            }

        return metrics

    def _compute_effectiveness(self) -> dict[str, dict]:
        stats: dict[str, dict] = {}
        for m in self._metrics.values():
            for ev in m.attack_events:
                s = stats.setdefault(ev.attack_type, {"attempts": 0, "injections": 0, "leakages": 0})
                s["attempts"]   += 1
                s["injections"] += int(ev.injection_executed)
                s["leakages"]   += int(ev.data_leaked)
        return {
            at: {
                "attempts":       s["attempts"],
                "injection_rate": round(s["injections"] / max(s["attempts"], 1), 3),
                "leakage_rate":   round(s["leakages"]   / max(s["attempts"], 1), 3),
            }
            for at, s in stats.items()
        }
