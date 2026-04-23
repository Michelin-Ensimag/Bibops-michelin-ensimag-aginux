import json
import os
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

import ollama

from src.bibops.it_support.memoire_courte import MemoCourTerme
from src.bibops.it_support.outils import (
    chercher_dans_kb,
    chercher_documentation_technique,
    get_tool_policy,
    normaliser_argument_outil,
    verifier_statut_serveur,
)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
DEFAULT_TRACE_DIR = os.path.join(BASE_DIR, "data", "runtime", "maestro")


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


KEYWORD_ROUTING = {
    "verifier_statut_serveur": ["vpn", "cisco", "outlook", "mail", "imprimante", "serveur", "service"],
    "chercher_documentation_technique": ["bitlocker", "documentation", "procedure", "tutoriel", "guide"],
    "chercher_dans_kb": ["crash", "lent", "mot de passe", "erreur", "ticket", "probleme"],
}


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _preview(text: Any, limit: int = 260) -> str:
    rendered = str(text).replace("\n", " ").strip()
    if len(rendered) <= limit:
        return rendered
    return rendered[: limit - 3] + "..."


def _extract_action(llm_content: str) -> tuple[str | None, str | None]:
    match = re.search(r'(?i)action:\s*([a-zA-Z_]+)\("([^"]*)"', llm_content)
    if not match:
        match = re.search(r"(?i)action:\s*([a-zA-Z_]+)\('([^']*)'", llm_content)
    if not match:
        return None, None
    return match.group(1), match.group(2)


def _routing_hint(ticket_utilisateur: str, outils_disponibles: list[Callable[[str], str]]) -> dict[str, Any]:
    lowered = ticket_utilisateur.lower()
    dispo = {o.__name__ for o in outils_disponibles}
    for outil_name, keywords in KEYWORD_ROUTING.items():
        if outil_name not in dispo:
            continue
        for keyword in keywords:
            if keyword in lowered:
                return {
                    "outil_recommande": outil_name,
                    "motif": f"mot-cle detecte: {keyword}",
                }
    return {
        "outil_recommande": None,
        "motif": "aucun mot-cle determinant detecte",
    }


def _extract_sources(tool_calls: list[ToolCallTrace]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for call in tool_calls:
        if call.statut != "ok":
            continue
        source_match = re.search(r"Source:\s*([A-Za-z0-9_.\-]+)", call.resultat_preview)
        pertinence_match = re.search(r"pertinence:\s*([0-9]*\.?[0-9]+)", call.resultat_preview)
        citation_ids = re.findall(r"\[([A-Za-z0-9_.\-]+)\]", call.resultat_preview)

        source = source_match.group(1) if source_match else None
        pertinence = None
        if pertinence_match:
            try:
                pertinence = float(pertinence_match.group(1))
            except ValueError:
                pertinence = None

        entry = {
            "outil": call.outil,
            "source": source,
            "pertinence": pertinence,
            "citations": citation_ids[:3],
            "resultat": call.resultat_preview,
        }
        sources.append(entry)
    return sources


def _extract_actions_from_text(text: str) -> list[str]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    numbered_or_bullet = []
    for line in lines:
        if re.match(r"^(\d+[\).]|[-*])\s+", line):
            numbered_or_bullet.append(re.sub(r"^(\d+[\).]|[-*])\s+", "", line).strip())
    if numbered_or_bullet:
        return numbered_or_bullet[:5]

    # Fallback: split by sentence chunks.
    by_sentence = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    return by_sentence[:3] if by_sentence else ["Aucune action explicite extraite."]


def _compute_confidence(tool_calls: list[ToolCallTrace], timed_out: bool) -> tuple[float, str, str]:
    if timed_out:
        return 0.2, "faible", "Le flux a atteint la limite d'iterations."

    success = sum(1 for c in tool_calls if c.statut == "ok")
    errors = sum(1 for c in tool_calls if c.statut in {"failed", "timeout", "unknown_tool", "invalid_argument"})
    duplicates = sum(1 for c in tool_calls if c.statut == "duplicate_blocked")

    score = 0.35 + (0.2 * success) - (0.12 * errors) - (0.05 * duplicates)

    # Signal RAG: boost si pertinence élevée, malus si contexte faible.
    rag_calls = [c for c in tool_calls if c.outil == "chercher_documentation_technique" and c.statut == "ok"]
    if rag_calls:
        distances = []
        for call in rag_calls:
            match = re.search(r"pertinence:\s*([0-9]*\.?[0-9]+)", call.resultat_preview)
            if match:
                try:
                    distances.append(float(match.group(1)))
                except ValueError:
                    continue
        if distances:
            best_distance = min(distances)
            if best_distance <= 0.6:
                score += 0.08
            elif best_distance >= 1.0:
                score -= 0.08

    score = max(0.05, min(0.95, score))

    if score >= 0.75:
        return round(score, 2), "eleve", "Au moins un outil a repondu sans erreur majeure."
    if score >= 0.5:
        return round(score, 2), "moyen", "La reponse est exploitable mais la couverture est partielle."
    return round(score, 2), "faible", "Les signaux d'execution indiquent un risque d'erreur." 


def _build_structured_answer(final_answer: str, trace: MaestroRunTrace, timed_out: bool) -> dict[str, Any]:
    confidence_score, confidence_label, confidence_reason = _compute_confidence(trace.tool_calls, timed_out)
    actions = _extract_actions_from_text(final_answer)
    sources = _extract_sources(trace.tool_calls)

    diagnostic = final_answer.split("\n")[0].strip() if final_answer.strip() else "Diagnostic indisponible"
    next_step = (
        "Escalader au support niveau 2 avec la trace run_id."
        if confidence_label == "faible"
        else "Appliquer les actions recommandees puis verifier l'etat du service."
    )

    return {
        "diagnostic": diagnostic,
        "actions_recommandees": actions,
        "sources": sources,
        "niveau_confiance": {
            "score": confidence_score,
            "label": confidence_label,
            "raison": confidence_reason,
        },
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

    last_status = "failed"
    last_result = f"Erreur outil '{nom_outil}' inconnue."

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
            last_result = (
                f"Erreur outil '{nom_outil}' (tentative {attempt}/{policy.max_retries + 1}): {exc}"
            )
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    duration_ms = int((time.perf_counter() - start) * 1000)
    return last_status, last_result, duration_ms, policy.max_retries + 1


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
    noms_outils = [outil.__name__ for outil in outils_disponibles]
    outils_map = {outil.__name__: outil for outil in outils_disponibles}

    trace.routing_hint = _routing_hint(ticket_utilisateur, outils_disponibles)

    systeme_prompt = f"""Tu es l'agent IA de support informatique BibOps chez Michelin.
Contexte : {contexte}

PROCEDURE OBLIGATOIRE — suis ces etapes dans l'ordre :
1. Lis le ticket et extrait le mot-cle principal (exemples: "vpn", "bitlocker", "outlook", "imprimante").
2. Appelle l'outil le plus adapte avec ce mot-cle.
3. Apres avoir recu le resultat de l'outil, redige ta reponse finale en francais a l'utilisateur.

FORMAT STRICT pour appeler un outil — ecris UNIQUEMENT cette ligne, rien avant, rien apres :
ACTION: nom_outil("mot_cle")

OUTILS DISPONIBLES : {noms_outils}
INTERDIT : inventer un nom d'outil. INTERDIT : appeler deux fois le meme outil avec le meme argument.
INTERDIT : ecrire ACTION dans ta reponse finale.

RECOMMANDATION DE ROUTAGE (guide non-bloquant) : {trace.routing_hint}

Exemples corrects :
- Ticket "VPN ne marche pas" → ACTION: verifier_statut_serveur("VPN")
- Ticket "recuperer mot de passe Bitlocker" → ACTION: chercher_documentation_technique("bitlocker")
- Ticket "Outlook crash" → ACTION: chercher_dans_kb("outlook crash")
"""

    print(f"\n [Utilisateur] : {ticket_utilisateur}")
    memoire.add_message("user", ticket_utilisateur)

    description_outils = "\nOUTILS DISPONIBLES :\n"
    for outil in outils_disponibles:
        description_outils += f"- {outil.__name__} : {outil.__doc__}\n"

    system_prompt = f"{systeme_prompt}\n{description_outils}"
    messages_a_envoyer = [{"role": "system", "content": system_prompt}] + memoire.get_messages()

    appels_deja_faits: set[tuple[str, str]] = set()
    final_answer = ""
    timed_out = True

    for etape in range(1, max_iterations + 1):
        llm_start = time.perf_counter()
        reponse = ollama.chat(model=modele, messages=messages_a_envoyer)
        llm_duration_ms = int((time.perf_counter() - llm_start) * 1000)
        contenu = reponse["message"]["content"]
        nom_outil_demande, argument = _extract_action(contenu)

        trace.llm_turns.append(
            LLMTurnTrace(
                etape=etape,
                duree_ms=llm_duration_ms,
                prompt_tokens=reponse.get("prompt_eval_count"),
                completion_tokens=reponse.get("eval_count"),
                action_detectee=bool(nom_outil_demande),
                reponse_preview=_preview(contenu),
            )
        )

        if not nom_outil_demande:
            final_answer = contenu
            timed_out = False
            print(f"\n[Agent (Réponse Finale)] : \n{contenu}")
            memoire.add_message("assistant", contenu)
            break

        argument = argument or ""
        print(f" [LLM veut utiliser l'outil] : {nom_outil_demande}('{argument}')")

        cle_appel = (nom_outil_demande, argument.lower().strip())
        if cle_appel in appels_deja_faits:
            dedup_msg = (
                f"STOP. Tu as déjà appelé '{nom_outil_demande}(\"{argument}\")' et obtenu un résultat. "
                f"N'appelle PLUS aucun outil. Rédige maintenant ta réponse finale à l'utilisateur "
                f"en utilisant uniquement les résultats déjà obtenus."
            )
            trace.tool_calls.append(
                ToolCallTrace(
                    etape=etape,
                    outil=nom_outil_demande,
                    argument=argument,
                    statut="duplicate_blocked",
                    duree_ms=0,
                    resultat_preview="Appel duplique bloque pour stabiliser la decision.",
                    attempts=0,
                )
            )
            messages_a_envoyer.append({"role": "assistant", "content": contenu})
            messages_a_envoyer.append({"role": "user", "content": dedup_msg})
            continue
        appels_deja_faits.add(cle_appel)

        status = "unknown_tool"
        tool_duration_ms = 0
        attempts = 0
        resultat_outil = (
            f"Erreur : L'outil '{nom_outil_demande}' n'existe pas. "
            f"Les seuls outils disponibles sont : {noms_outils}. Utilise UNIQUEMENT un de ces outils."
        )

        outil = outils_map.get(nom_outil_demande)
        if outil is not None:
            status, resultat_outil, tool_duration_ms, attempts = _execute_tool_with_policy(
                outil=outil,
                nom_outil=nom_outil_demande,
                argument=argument,
            )

        trace.tool_calls.append(
            ToolCallTrace(
                etape=etape,
                outil=nom_outil_demande,
                argument=argument,
                statut=status,
                duree_ms=tool_duration_ms,
                resultat_preview=_preview(resultat_outil, limit=520),
                attempts=attempts,
            )
        )

        print(f"   -> Résultat : {_preview(resultat_outil, limit=150)}")

        messages_a_envoyer.append({"role": "assistant", "content": contenu})
        messages_a_envoyer.append({"role": "user", "content": f"Résultat de l'outil : {resultat_outil}"})

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
        payload = {
            "run_id": trace.run_id,
            "reponse_finale": final_answer,
        }
        if structured_output:
            payload["resultat_structure"] = trace.structured_answer
        if return_trace:
            payload["trace"] = asdict(trace)
        return payload

    return final_answer


def evaluer_agent_sur_tickets(
    cas_tests: list[dict[str, str]],
    outils_disponibles: list[Callable[[str], str]],
    modele: str = "phi3:latest",
    save_trace: bool = True,
    trace_dir: str | None = None,
) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    total_ms = 0
    total_tool_calls = 0
    total_tool_success = 0
    total_tool_retries = 0

    for idx, case in enumerate(cas_tests, start=1):
        contexte = case.get("contexte", "")
        ticket = case.get("ticket") or case.get("texte_utilisateur") or ""
        result = lancer_agent(
            contexte=contexte,
            ticket_utilisateur=ticket,
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

        runs.append(
            {
                "index": idx,
                "ticket": ticket,
                "run_id": result["run_id"],
                "outcome": trace.get("outcome"),
                "latence_ms": trace.get("total_duree_ms"),
                "tool_calls": len(tool_calls),
                "tool_success": success_calls,
                "tool_retries": retries,
                "confiance": result["resultat_structure"]["niveau_confiance"],
                "diagnostic": result["resultat_structure"]["diagnostic"],
            }
        )

    n = max(1, len(runs))
    tool_success_rate = (total_tool_success / max(1, total_tool_calls))

    return {
        "modele": modele,
        "nombre_cas": len(runs),
        "latence_moyenne_ms": round(total_ms / n, 2),
        "appels_outils_total": total_tool_calls,
        "taux_succes_outils": round(tool_success_rate, 4),
        "retries_outils_total": total_tool_retries,
        "runs": runs,
    }


if __name__ == "__main__":
    print("[ AGENT BIBOPS ]")

    mes_outils = [
        verifier_statut_serveur,
        chercher_documentation_technique,
        chercher_dans_kb,
    ]

    demo = lancer_agent(
        "L'entreprise est Michelin. Le VPN principal est Cisco.",
        "Impossible de me connecter au VPN ce matin.",
        outils_disponibles=mes_outils,
        return_trace=True,
        structured_output=True,
        save_trace=True,
    )
    print("\n=== RESULTAT STRUCTURE ===")
    print(json.dumps(demo["resultat_structure"], ensure_ascii=False, indent=2))
