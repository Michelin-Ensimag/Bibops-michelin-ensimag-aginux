import json
import os
import re
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from openai import OpenAI
from pydantic import BaseModel

from .memory import MemoCourTerme
from .tools import (
    chercher_dans_kb,
    chercher_documentation_technique,
    get_tool_policy,
    normaliser_argument_outil,
    verifier_statut_serveur,
)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
DEFAULT_TRACE_DIR = os.path.join(BASE_DIR, "data", "runtime", "maestro")


# ── Structured output contract ────────────────────────────────────────────────

class AgentDecision(BaseModel):
    """What the LLM returns each turn: either a tool call or a final answer."""
    tool: str | None = None
    argument: str | None = None
    final_answer: str | None = None


# ── Trace dataclasses ─────────────────────────────────────────────────────────

@dataclass
class ToolCallTrace:
    etape: int
    outil: str
    argument: str
    statut: str
    duree_ms: int
    resultat_preview: str
    attempts: int = 0


@dataclass
class LLMTurnTrace:
    etape: int
    duree_ms: int
    prompt_tokens: int | None
    completion_tokens: int | None
    action_detectee: bool
    reponse_preview: str


@dataclass
class MaestroRunTrace:
    run_id: str
    started_at_utc: str
    ended_at_utc: str | None = None
    contexte: str = ""
    ticket_utilisateur: str = ""
    modele: str = ""
    routing_hint: dict[str, Any] = field(default_factory=dict)
    llm_turns: list[LLMTurnTrace] = field(default_factory=list)
    tool_calls: list[ToolCallTrace] = field(default_factory=list)
    final_answer: str = ""
    structured_answer: dict[str, Any] = field(default_factory=dict)
    outcome: str = ""
    total_duree_ms: int = 0
    trace_file: str | None = None


# ── Routing hint ──────────────────────────────────────────────────────────────

KEYWORD_ROUTING = {
    "verifier_statut_serveur": ["vpn", "cisco", "outlook", "mail", "imprimante", "serveur", "service"],
    "chercher_documentation_technique": ["bitlocker", "documentation", "procedure", "tutoriel", "guide"],
    "chercher_dans_kb": ["crash", "lent", "mot de passe", "erreur", "ticket", "probleme"],
}


def _routing_hint(ticket_utilisateur: str, outils_disponibles: list[Callable[[str], str]]) -> dict[str, Any]:
    lowered = ticket_utilisateur.lower()
    dispo = {o.__name__ for o in outils_disponibles}
    for outil_name, keywords in KEYWORD_ROUTING.items():
        if outil_name not in dispo:
            continue
        for keyword in keywords:
            if keyword in lowered:
                return {"outil_recommande": outil_name, "motif": f"mot-cle detecte: {keyword}"}
    return {"outil_recommande": None, "motif": "aucun mot-cle determinant detecte"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _preview(text: Any, limit: int = 260) -> str:
    rendered = str(text).replace("\n", " ").strip()
    return rendered if len(rendered) <= limit else rendered[: limit - 3] + "..."


def _extract_sources(tool_calls: list[ToolCallTrace]) -> list[dict[str, Any]]:
    sources = []
    for call in tool_calls:
        if call.statut != "ok":
            continue
        source_match = re.search(r"Source:\s*([A-Za-z0-9_.\-]+)", call.resultat_preview)
        pertinence_match = re.search(r"pertinence:\s*([0-9]*\.?[0-9]+)", call.resultat_preview)
        citation_ids = re.findall(r"\[([A-Za-z0-9_.\-]+)\]", call.resultat_preview)
        pertinence = None
        if pertinence_match:
            try:
                pertinence = float(pertinence_match.group(1))
            except ValueError:
                pass
        sources.append({
            "outil": call.outil,
            "source": source_match.group(1) if source_match else None,
            "pertinence": pertinence,
            "citations": citation_ids[:3],
            "resultat": call.resultat_preview,
        })
    return sources


def _extract_actions_from_text(text: str) -> list[str]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    numbered_or_bullet = [
        re.sub(r"^(\d+[\).]|[-*])\s+", "", line).strip()
        for line in lines
        if re.match(r"^(\d+[\).]|[-*])\s+", line)
    ]
    if numbered_or_bullet:
        return numbered_or_bullet[:5]
    by_sentence = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    return by_sentence[:3] if by_sentence else ["Aucune action explicite extraite."]


def _compute_confidence(tool_calls: list[ToolCallTrace], timed_out: bool) -> tuple[float, str, str]:
    if timed_out:
        return 0.2, "faible", "Le flux a atteint la limite d'iterations."

    success = sum(1 for c in tool_calls if c.statut == "ok")
    errors = sum(1 for c in tool_calls if c.statut in {"failed", "timeout", "unknown_tool", "invalid_argument"})
    duplicates = sum(1 for c in tool_calls if c.statut == "duplicate_blocked")
    score = 0.35 + (0.2 * success) - (0.12 * errors) - (0.05 * duplicates)

    rag_calls = [c for c in tool_calls if c.outil == "chercher_documentation_technique" and c.statut == "ok"]
    for call in rag_calls:
        match = re.search(r"pertinence:\s*([0-9]*\.?[0-9]+)", call.resultat_preview)
        if match:
            try:
                d = float(match.group(1))
                score += 0.08 if d <= 0.6 else (-0.08 if d >= 1.0 else 0)
            except ValueError:
                pass

    score = max(0.05, min(0.95, score))
    if score >= 0.75:
        return round(score, 2), "eleve", "Au moins un outil a repondu sans erreur majeure."
    if score >= 0.5:
        return round(score, 2), "moyen", "La reponse est exploitable mais la couverture est partielle."
    return round(score, 2), "faible", "Les signaux d'execution indiquent un risque d'erreur."


def _build_structured_answer(final_answer: str, trace: MaestroRunTrace, timed_out: bool) -> dict[str, Any]:
    confidence_score, confidence_label, confidence_reason = _compute_confidence(trace.tool_calls, timed_out)
    diagnostic = final_answer.split("\n")[0].strip() if final_answer.strip() else "Diagnostic indisponible"
    next_step = (
        "Escalader au support niveau 2 avec la trace run_id."
        if confidence_label == "faible"
        else "Appliquer les actions recommandees puis verifier l'etat du service."
    )
    return {
        "diagnostic": diagnostic,
        "actions_recommandees": _extract_actions_from_text(final_answer),
        "sources": _extract_sources(trace.tool_calls),
        "niveau_confiance": {"score": confidence_score, "label": confidence_label, "raison": confidence_reason},
        "prochaine_etape": next_step,
        "reponse_utilisateur": final_answer,
    }


def _save_trace(trace: MaestroRunTrace, trace_dir: str | None) -> str:
    target_dir = trace_dir or DEFAULT_TRACE_DIR
    os.makedirs(target_dir, exist_ok=True)
    target_file = os.path.join(target_dir, "maestro_runs.jsonl")
    with open(target_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(trace), ensure_ascii=False) + "\n")
    return target_file


# ── Tool execution ────────────────────────────────────────────────────────────

def _execute_tool_with_policy(
    outil: Callable[[str], str],
    nom_outil: str,
    argument: str,
) -> tuple[str, str, int, int]:
    policy = get_tool_policy(nom_outil)
    start = time.perf_counter()

    try:
        normalized_arg = normaliser_argument_outil(nom_outil, argument)
    except ValueError as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return "invalid_argument", f"Argument invalide pour '{nom_outil}': {exc}", duration_ms, 0

    last_status, last_result = "failed", f"Erreur outil '{nom_outil}' inconnue."

    for attempt in range(1, policy.max_retries + 2):
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(outil, normalized_arg)
        try:
            result = future.result(timeout=policy.timeout_s)
            duration_ms = int((time.perf_counter() - start) * 1000)
            executor.shutdown(wait=False, cancel_futures=True)
            return "ok", str(result), duration_ms, attempt
        except FuturesTimeoutError:
            last_status = "timeout"
            last_result = (
                f"Timeout outil '{nom_outil}' (> {policy.timeout_s:.1f}s) "
                f"apres tentative {attempt}/{policy.max_retries + 1}."
            )
            future.cancel()
        except Exception as exc:  # pragma: no cover
            last_status = "failed"
            last_result = f"Erreur outil '{nom_outil}' (tentative {attempt}/{policy.max_retries + 1}): {exc}"
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    return last_status, last_result, int((time.perf_counter() - start) * 1000), policy.max_retries + 1


# ── LLM call (thin wrapper kept separate so tests can patch it) ───────────────

def _make_client() -> OpenAI:
    return OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")


def _call_llm(
    client: OpenAI,
    model: str,
    messages: list[dict],
    response_model: type[BaseModel],
) -> BaseModel:
    raw = client.chat.completions.create(
        model=model,
        messages=messages,
        response_format={"type": "json_object"},
    )
    return response_model.model_validate_json(raw.choices[0].message.content)


# ── Main agent loop ───────────────────────────────────────────────────────────

def lancer_agent(
    contexte,
    ticket_utilisateur,
    outils_disponibles,
    modele="phi3:latest",
    return_trace: bool = False,
    structured_output: bool = False,
    save_trace: bool = False,
    trace_dir: str | None = None,
    max_iterations: int = 5,
):
    run_id = str(uuid.uuid4())
    start = time.perf_counter()
    trace = MaestroRunTrace(
        run_id=run_id,
        started_at_utc=_now_utc_iso(),
        contexte=contexte,
        ticket_utilisateur=ticket_utilisateur,
        modele=modele,
    )

    memoire = MemoCourTerme(max_messages=50)
    noms_outils = [o.__name__ for o in outils_disponibles]
    outils_map = {o.__name__: o for o in outils_disponibles}
    client = _make_client()

    trace.routing_hint = _routing_hint(ticket_utilisateur, outils_disponibles)

    description_outils = "\n".join(f"- {o.__name__} : {o.__doc__}" for o in outils_disponibles)
    system_prompt = f"""Tu es l'agent IA de support informatique BibOps chez Michelin.
Contexte : {contexte}

PROCEDURE :
1. Lis le ticket utilisateur.
2. Si tu as besoin d'un outil, retourne tool=<nom_outil> et argument=<mot_cle>, final_answer=null.
3. Quand tu as la réponse, retourne tool=null et final_answer=<ta_reponse_en_francais>.

OUTILS DISPONIBLES : {noms_outils}
RECOMMANDATION DE ROUTAGE (guide non-bloquant) : {trace.routing_hint}

{description_outils}"""

    print(f"\n [Utilisateur] : {ticket_utilisateur}")
    memoire.add_message("user", ticket_utilisateur)
    messages_a_envoyer = [{"role": "system", "content": system_prompt}] + memoire.get_messages()

    appels_deja_faits: set[tuple[str, str]] = set()
    final_answer = ""
    timed_out = True

    for etape in range(1, max_iterations + 1):
        llm_start = time.perf_counter()
        decision: AgentDecision = _call_llm(client, modele, messages_a_envoyer, AgentDecision)
        llm_duration_ms = int((time.perf_counter() - llm_start) * 1000)

        trace.llm_turns.append(LLMTurnTrace(
            etape=etape,
            duree_ms=llm_duration_ms,
            prompt_tokens=None,
            completion_tokens=None,
            action_detectee=decision.tool is not None,
            reponse_preview=_preview(decision.model_dump()),
        ))

        if decision.tool is None:
            final_answer = decision.final_answer or ""
            timed_out = False
            print(f"\n[Agent (Réponse Finale)] :\n{final_answer}")
            memoire.add_message("assistant", final_answer)
            break

        tool_name = decision.tool
        argument = decision.argument or ""
        print(f" [LLM veut utiliser l'outil] : {tool_name}('{argument}')")

        cle_appel = (tool_name, argument.lower().strip())
        if cle_appel in appels_deja_faits:
            dedup_msg = (
                f"Tu as déjà appelé '{tool_name}(\"{argument}\")' et obtenu un résultat. "
                f"Rédige maintenant ta réponse finale à l'utilisateur."
            )
            trace.tool_calls.append(ToolCallTrace(
                etape=etape, outil=tool_name, argument=argument,
                statut="duplicate_blocked", duree_ms=0,
                resultat_preview="Appel duplique bloque.", attempts=0,
            ))
            memoire.add_message("assistant", f"[outil: {tool_name}({argument})]")
            memoire.add_message("user", dedup_msg)
            messages_a_envoyer = [{"role": "system", "content": system_prompt}] + memoire.get_messages()
            continue
        appels_deja_faits.add(cle_appel)

        outil = outils_map.get(tool_name)
        if outil is None:
            status = "unknown_tool"
            resultat_outil = f"L'outil '{tool_name}' n'existe pas. Outils disponibles : {noms_outils}."
            tool_duration_ms, attempts = 0, 0
        else:
            status, resultat_outil, tool_duration_ms, attempts = _execute_tool_with_policy(
                outil=outil, nom_outil=tool_name, argument=argument,
            )

        trace.tool_calls.append(ToolCallTrace(
            etape=etape, outil=tool_name, argument=argument,
            statut=status, duree_ms=tool_duration_ms,
            resultat_preview=_preview(resultat_outil, limit=520),
            attempts=attempts,
        ))

        print(f"   -> Résultat : {_preview(resultat_outil, limit=150)}")

        memoire.add_message("assistant", f"[outil: {tool_name}({argument})]")
        memoire.add_message("user", f"Résultat de l'outil : {resultat_outil}")
        messages_a_envoyer = [{"role": "system", "content": system_prompt}] + memoire.get_messages()

    if timed_out:
        final_answer = (
            "Je n'ai pas pu résoudre le problème dans le temps imparti. "
            "Merci de contacter le support de niveau 2."
        )
        print(f"\n[Agent (Timeout)] : {final_answer}")

    trace.ended_at_utc = _now_utc_iso()
    trace.total_duree_ms = int((time.perf_counter() - start) * 1000)
    trace.final_answer = final_answer
    trace.structured_answer = _build_structured_answer(final_answer, trace, timed_out=timed_out)
    trace.outcome = "timeout" if timed_out else "completed"

    if save_trace:
        trace.trace_file = _save_trace(trace, trace_dir)

    if return_trace or structured_output:
        payload: dict[str, Any] = {"run_id": trace.run_id, "reponse_finale": final_answer}
        if structured_output:
            payload["resultat_structure"] = trace.structured_answer
        if return_trace:
            payload["trace"] = asdict(trace)
        return payload

    return final_answer


# ── Batch evaluation ──────────────────────────────────────────────────────────

def evaluer_agent_sur_tickets(
    cas_tests: list[dict[str, str]],
    outils_disponibles: list[Callable[[str], str]],
    modele: str = "phi3:latest",
    save_trace: bool = True,
    trace_dir: str | None = None,
) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    total_ms = total_tool_calls = total_tool_success = total_tool_retries = 0

    for idx, case in enumerate(cas_tests, start=1):
        result = lancer_agent(
            contexte=case.get("contexte", ""),
            ticket_utilisateur=case.get("ticket") or case.get("texte_utilisateur") or "",
            outils_disponibles=outils_disponibles,
            modele=modele,
            return_trace=True,
            structured_output=True,
            save_trace=save_trace,
            trace_dir=trace_dir,
        )
        trace = result["trace"]
        tool_calls = trace.get("tool_calls", [])
        success_calls = sum(1 for c in tool_calls if c.get("statut") == "ok")
        retries = sum(max(0, int(c.get("attempts", 0)) - 1) for c in tool_calls)
        total_tool_calls += len(tool_calls)
        total_tool_success += success_calls
        total_tool_retries += retries
        total_ms += trace.get("total_duree_ms", 0)
        runs.append({
            "index": idx,
            "ticket": case.get("ticket") or case.get("texte_utilisateur") or "",
            "run_id": result["run_id"],
            "outcome": trace.get("outcome"),
            "latence_ms": trace.get("total_duree_ms"),
            "tool_calls": len(tool_calls),
            "tool_success": success_calls,
            "tool_retries": retries,
            "confiance": result["resultat_structure"]["niveau_confiance"],
            "diagnostic": result["resultat_structure"]["diagnostic"],
        })

    n = max(1, len(runs))
    return {
        "modele": modele,
        "nombre_cas": len(runs),
        "latence_moyenne_ms": round(total_ms / n, 2),
        "appels_outils_total": total_tool_calls,
        "taux_succes_outils": round(total_tool_success / max(1, total_tool_calls), 4),
        "retries_outils_total": total_tool_retries,
        "runs": runs,
    }


if __name__ == "__main__":
    print("[ AGENT BIBOPS ]")
    demo = lancer_agent(
        "L'entreprise est Michelin. Le VPN principal est Cisco.",
        "Impossible de me connecter au VPN ce matin.",
        outils_disponibles=[verifier_statut_serveur, chercher_documentation_technique, chercher_dans_kb],
        return_trace=True,
        structured_output=True,
        save_trace=True,
    )
    print("\n=== RESULTAT STRUCTURE ===")
    print(json.dumps(demo["resultat_structure"], ensure_ascii=False, indent=2))
