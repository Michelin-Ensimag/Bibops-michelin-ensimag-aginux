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

from src.common.config import DEFAULT_AGENT_MODEL, DEFAULT_AGENT_PROVIDER, MODEL_REQUEST_TIMEOUT_S, normalize_provider
from src.common.llm_clients import get_copilot_client

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
    resultat: str = ""
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
    provider: str = ""
    modele: str = ""
    routing_hint: dict[str, Any] = field(default_factory=dict)
    forced_initial_tool: bool = False
    empty_answer_repair_count: int = 0
    llm_turns: list[LLMTurnTrace] = field(default_factory=list)
    tool_calls: list[ToolCallTrace] = field(default_factory=list)
    final_answer: str = ""
    structured_answer: dict[str, Any] = field(default_factory=dict)
    outcome: str = ""
    total_duree_ms: int = 0
    trace_file: str | None = None


# ── Routing hint ──────────────────────────────────────────────────────────────

KEYWORD_ROUTING_RULES = [
    {
        "outil": "chercher_dans_kb",
        "argument": None,
        "keywords": [
            "applications internes",
            "application interne",
            "vpn se connecte",
            "vpn connecté",
            "vpn connecte",
            "aucune application interne",
        ],
    },
    {
        "outil": "verifier_statut_serveur",
        "argument": "vpn",
        "keywords": ["vpn", "cisco anyconnect", "anyconnect"],
    },
    {
        "outil": "chercher_documentation_technique",
        "argument": "bitlocker",
        "keywords": ["bitlocker", "documentation", "procédure détaillée", "procedure detaillee"],
    },
    {
        "outil": "chercher_dans_kb",
        "argument": None,
        "keywords": [
            "outlook",
            "teams",
            "windows",
            "mot de passe",
            "imprimante",
            "imprimer",
            "wifi",
            "proxy",
            "sap",
            "scanner",
            "bluetooth",
            "dossier réseau",
            "dossier reseau",
            "administrateur local",
            "installer un logiciel",
            "installation logiciel",
            "logiciel",
            "python",
            "node.js",
            "docker",
            "badge usb",
            "certificat",
            "boîte aux lettres",
            "boite aux lettres",
            "recto-verso",
            "partage d'écran",
            "partage d'ecran",
            "intranet",
            "pdf vides",
        ],
    },
    {
        "outil": "chercher_dans_kb",
        "argument": None,
        "keywords": ["crash", "lent", "erreur", "ticket", "probleme", "problème"],
    },
]


def _routing_hint(ticket_utilisateur: str, outils_disponibles: list[Callable[[str], str]]) -> dict[str, Any]:
    lowered = ticket_utilisateur.lower()
    dispo = {o.__name__ for o in outils_disponibles}
    for rule in KEYWORD_ROUTING_RULES:
        outil_name = str(rule["outil"])
        if outil_name not in dispo:
            continue
        for keyword in rule["keywords"]:
            if keyword in lowered:
                argument = str(rule["argument"] or ticket_utilisateur)
                return {
                    "outil_recommande": outil_name,
                    "argument_recommande": argument,
                    "motif": f"mot-cle detecte: {keyword}",
                }
    return {"outil_recommande": None, "motif": "aucun mot-cle determinant detecte"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _preview(text: Any, limit: int = 260) -> str:
    rendered = str(text).replace("\n", " ").strip()
    return rendered if len(rendered) <= limit else rendered[: limit - 3] + "..."


def _tool_result_text(call: ToolCallTrace) -> str:
    return call.resultat or call.resultat_preview


def _extract_sources(tool_calls: list[ToolCallTrace]) -> list[dict[str, Any]]:
    sources = []
    for call in tool_calls:
        if call.statut != "ok":
            continue
        result_text = _tool_result_text(call)
        source_match = re.search(r"Source:\s*([A-Za-z0-9_.\-]+)", result_text)
        pertinence_match = re.search(r"pertinence:\s*([0-9]*\.?[0-9]+)", result_text)
        citation_ids = re.findall(r"\[([A-Za-z0-9_.\-]+)\]", result_text)
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
            "resultat": _preview(result_text, 520),
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


def _first_solution_block(text: str) -> str:
    if "--- SOLUTION 1 ---" not in text:
        return text.strip()
    return re.split(r"\n---\s*SOLUTION\s+2\s*---", text, maxsplit=1, flags=re.IGNORECASE)[0].strip()


def _extract_field(text: str, label_pattern: str) -> str:
    match = re.search(rf"^{label_pattern}\s*:\s*(.+)$", text, flags=re.IGNORECASE | re.MULTILINE)
    return match.group(1).strip() if match else ""


def _extract_section(text: str, header_pattern: str) -> list[str]:
    match = re.search(rf"^{header_pattern}\s*:\s*(.*)$", text, flags=re.IGNORECASE | re.MULTILINE)
    if not match:
        return []

    inline = match.group(1).strip()
    rest = text[match.end():]
    stop = re.search(
        r"^(?:ID|Score KB|Probl[eè]me|Cat[eé]gorie|Priorit[eé]|Statut|Diagnostic|Actions|R[eé]solution|Escalade)\s*:",
        rest,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    block = rest[: stop.start()] if stop else rest
    content = "\n".join(part for part in (inline, block.strip()) if part)
    if not content:
        return []
    return [item for item in _extract_actions_from_text(content) if len(item) > 4]


def _compose_answer_from_tool_call(ticket: str, call: ToolCallTrace) -> str:
    if call.statut != "ok":
        return ""

    result_text = _first_solution_block(_tool_result_text(call))
    if not result_text or "Aucune solution trouvée" in result_text:
        return ""

    problem = _extract_field(result_text, r"Probl[eè]me")
    category = _extract_field(result_text, r"Cat[eé]gorie")
    priority = _extract_field(result_text, r"Priorit[eé]")
    status = _extract_field(result_text, r"Statut")
    diagnostic_lines = _extract_section(result_text, r"Diagnostic")
    resolution_lines = _extract_section(result_text, r"R[eé]solution")
    action_lines = _extract_section(result_text, r"Actions")
    escalation = _extract_field(result_text, r"Escalade")

    diagnostic = status or problem
    if diagnostic_lines:
        diagnostic = f"{diagnostic} — {diagnostic_lines[0]}" if diagnostic else diagnostic_lines[0]

    actions = resolution_lines or action_lines
    if not actions:
        actions = _extract_actions_from_text(result_text)

    cleaned_actions = []
    for action in actions:
        cleaned = re.sub(r"^\s*\d+[\).]\s*", "", action).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        if cleaned and cleaned.lower() not in {a.lower() for a in cleaned_actions}:
            cleaned_actions.append(cleaned)

    if not diagnostic and not cleaned_actions:
        return ""

    lines = [
        f"Diagnostic : {diagnostic or f'procédure trouvée pour le ticket : {ticket}'}",
    ]
    if category:
        lines.append(f"Catégorie : {category}")
    if priority:
        lines.append(f"Priorité : {priority}")

    if cleaned_actions:
        lines.extend(["", "Étapes recommandées :"])
        for idx, action in enumerate(cleaned_actions[:6], start=1):
            lines.append(f"{idx}. {action}")

    if escalation:
        lines.extend(["", f"Escalade : {escalation}"])

    return "\n".join(lines).strip()


def _synthesize_answer_from_tools(ticket: str, trace: MaestroRunTrace) -> str:
    ok_calls = [call for call in trace.tool_calls if call.statut == "ok"]
    for call in reversed(ok_calls):
        answer = _compose_answer_from_tool_call(ticket, call)
        if answer:
            return answer
    return ""


def _significant_tokens(text: str) -> set[str]:
    stopwords = {
        "avec", "cette", "dans", "des", "donc", "est", "les", "pour", "que", "qui", "sur", "une",
        "vous", "votre", "ticket", "solution", "probleme", "problème", "outil", "resultat", "résultat",
    }
    tokens = {
        tok.lower()
        for tok in re.findall(r"[A-Za-zÀ-ÿ0-9]+", text or "")
        if len(tok) >= 4
    }
    return {tok for tok in tokens if tok not in stopwords}


def _answer_is_grounded_in_tools(final_answer: str, trace: MaestroRunTrace) -> bool:
    if not any(call.statut == "ok" for call in trace.tool_calls):
        return True

    lowered = final_answer.lower()
    suspicious_markers = [
        "si l'utilisateur",
        "sans utiliser les outils",
        "résultat précédent",
        "resultat precedent",
        "première solution",
        "premiere solution",
        "je ne possède actuellement que",
        "je ne possede actuellement que",
        "procédez comme suit :",
        "procedez comme suit :",
    ]
    if any(marker in lowered for marker in suspicious_markers):
        return False

    tool_text = "\n".join(_tool_result_text(call) for call in trace.tool_calls if call.statut == "ok")
    answer_tokens = _significant_tokens(final_answer)
    tool_tokens = _significant_tokens(tool_text)
    if not answer_tokens or not tool_tokens:
        return False

    overlap = answer_tokens & tool_tokens
    return len(overlap) >= min(3, len(answer_tokens))


def _extract_llm_usage(raw: Any) -> tuple[int | None, int | None]:
    usage = getattr(raw, "usage", None)
    if usage is None and isinstance(raw, dict):
        usage = raw.get("usage")
    if usage is None:
        return None, None

    def _get(name: str) -> int | None:
        value = usage.get(name) if isinstance(usage, dict) else getattr(usage, name, None)
        return value if isinstance(value, int) else None

    return _get("prompt_tokens"), _get("completion_tokens")


def _get_decision_usage(decision: BaseModel) -> tuple[int | None, int | None]:
    usage = getattr(decision, "_bibops_usage", None)
    if not isinstance(usage, dict):
        return None, None
    prompt = usage.get("prompt_tokens")
    completion = usage.get("completion_tokens")
    return (
        prompt if isinstance(prompt, int) else None,
        completion if isinstance(completion, int) else None,
    )


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


def _should_disable_it_tools(contexte: str, ticket: str) -> bool:
    context = (contexte or "").lower()
    text = f"{contexte} {ticket}".lower()
    it_context_markers = [
        "technicien support it",
        "support it",
        "helpdesk",
        "service desk",
    ]
    if any(marker in context for marker in it_context_markers):
        return False

    non_it_markers = [
        "ressources humaines",
        "expert rh",
        "juriste",
        "juridique",
        "finance voyage",
        "politiques de voyage",
        "politiques de travail",
        "télétravail et politiques",
        "note de frais",
        "remboursement",
        "congé",
        "congés",
        "bulletin de paie",
        "arrêt maladie",
    ]
    it_markers = [
        "vpn",
        "cisco",
        "outlook",
        "teams",
        "windows",
        "imprimante",
        "serveur",
        "proxy",
        "sap",
        "scanner",
        "wifi",
        "bluetooth",
        "bitlocker",
        "mot de passe",
        "dossier réseau",
    ]
    context_is_non_it = any(marker in context for marker in non_it_markers)
    return context_is_non_it or (any(marker in text for marker in non_it_markers) and not any(marker in text for marker in it_markers))


def _fallback_final_answer(ticket: str, trace: MaestroRunTrace, *, timed_out: bool) -> str:
    ok_calls = [call for call in trace.tool_calls if call.statut == "ok"]
    if ok_calls:
        lines = [
            "Je n'ai pas obtenu de réponse finale fiable du modèle, mais les outils donnent un diagnostic exploitable.",
            "",
            f"Ticket : {ticket}",
            "",
            "Éléments vérifiés :",
        ]
        for call in ok_calls[:3]:
            lines.append(f"- {call.outil}({call.argument}) : {call.resultat_preview}")
        lines.extend(
            [
                "",
                "Actions recommandées :",
                "1. Appliquer les étapes de diagnostic ou de résolution retournées par l'outil.",
                "2. Si le service est indiqué hors ligne, informer l'utilisateur qu'un incident est en cours et éviter les manipulations locales inutiles.",
                "3. Si le service est en ligne mais le problème persiste, collecter le message d'erreur exact, l'heure de l'incident et le poste concerné.",
                "4. Escalader au support niveau 2 avec ces informations si aucune étape ne résout le problème.",
            ]
        )
        return "\n".join(lines)

    if _should_disable_it_tools(trace.contexte, ticket):
        return (
            "Je n'ai pas accès aux données personnelles ou aux politiques internes précises nécessaires pour répondre avec certitude. "
            "Consulte le portail métier Michelin correspondant, vérifie la rubrique liée à ta demande, puis contacte le service responsable "
            "si l'information n'est pas visible."
        )

    reason = "dans le temps imparti" if timed_out else "avec les informations disponibles"
    return (
        f"Je n'ai pas pu produire un diagnostic fiable {reason}. "
        "Commence par redémarrer l'application ou le poste concerné, vérifier la connexion réseau, noter le message d'erreur exact "
        "et l'heure d'apparition, puis escalade au support niveau 2 si le problème persiste."
    )


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


def _execute_and_record_tool_call(
    *,
    etape: int,
    tool_name: str,
    argument: str,
    outils_map: dict[str, Callable[[str], str]],
    noms_outils: list[str],
    appels_deja_faits: set[tuple[str, str]],
    trace: MaestroRunTrace,
    memoire: MemoCourTerme,
) -> str:
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
            resultat_preview="Appel duplique bloque.", resultat="Appel duplique bloque.", attempts=0,
        ))
        memoire.add_message("assistant", f"[outil: {tool_name}({argument})]")
        memoire.add_message("user", dedup_msg)
        return "duplicate_blocked"
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
        resultat=str(resultat_outil),
        attempts=attempts,
    ))

    print(f"   -> Résultat : {_preview(resultat_outil, limit=150)}")

    memoire.add_message("assistant", f"[outil: {tool_name}({argument})]")
    memoire.add_message("user", f"Résultat de l'outil : {resultat_outil}")
    return status


# ── LLM call (thin wrapper kept separate so tests can patch it) ───────────────

def _make_client(provider: str = DEFAULT_AGENT_PROVIDER) -> OpenAI:
    provider = normalize_provider(provider)
    if provider == "copilot":
        return get_copilot_client()
    return OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")


def _call_llm(
    client: OpenAI,
    model: str,
    messages: list[dict],
    response_model: type[BaseModel],
    timeout_s: int = MODEL_REQUEST_TIMEOUT_S,
) -> BaseModel:
    raw = client.chat.completions.create(
        model=model,
        messages=messages,
        response_format={"type": "json_object"},
        timeout=timeout_s,
    )
    parsed = response_model.model_validate_json(raw.choices[0].message.content)
    prompt_tokens, completion_tokens = _extract_llm_usage(raw)
    object.__setattr__(
        parsed,
        "_bibops_usage",
        {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
    )
    return parsed


# ── Main agent loop ───────────────────────────────────────────────────────────

def lancer_agent(
    contexte,
    ticket_utilisateur,
    outils_disponibles,
    modele=DEFAULT_AGENT_MODEL,
    modele_provider: str = DEFAULT_AGENT_PROVIDER,
    return_trace: bool = False,
    structured_output: bool = False,
    save_trace: bool = False,
    trace_dir: str | None = None,
    max_iterations: int = 5,
    force_initial_tool: bool = False,
    deterministic_tool_answer: bool = False,
):
    run_id = str(uuid.uuid4())
    start = time.perf_counter()
    trace = MaestroRunTrace(
        run_id=run_id,
        started_at_utc=_now_utc_iso(),
        contexte=contexte,
        ticket_utilisateur=ticket_utilisateur,
        provider=normalize_provider(modele_provider),
        modele=modele,
    )

    memoire = MemoCourTerme(max_messages=50)
    outils_effectifs = [] if _should_disable_it_tools(contexte, ticket_utilisateur) else outils_disponibles
    noms_outils = [o.__name__ for o in outils_effectifs]
    outils_map = {o.__name__: o for o in outils_effectifs}
    client = _make_client(modele_provider)

    if outils_effectifs:
        trace.routing_hint = _routing_hint(ticket_utilisateur, outils_effectifs)
    else:
        trace.routing_hint = {
            "outil_recommande": None,
            "motif": "contexte hors IT ou demande personnelle: reponse directe sans outils IT",
        }

    description_outils = "\n".join(f"- {o.__name__} : {o.__doc__}" for o in outils_effectifs)
    if not description_outils:
        description_outils = "Aucun outil pertinent n'est disponible pour ce ticket. Réponds directement."
    system_prompt = f"""Tu es l'agent IA BibOps chez Michelin. Respecte strictement le contexte métier fourni.
Contexte : {contexte}

PROCEDURE :
1. Lis le ticket utilisateur.
2. Si le ticket est RH, juridique, finance, voyage ou personnel, réponds directement selon le contexte et N'UTILISE PAS les outils IT.
3. Si la demande exige une donnée personnelle inaccessible (solde de congés, paie, remboursement précis), explique la limite et indique le portail/service à contacter.
4. Pour un ticket IT uniquement, si tu as besoin d'un outil disponible, retourne tool=<nom_outil> et argument=<mot_cle>, final_answer=null.
5. Quand tu as assez d'information, retourne tool=null et final_answer=<ta_reponse_en_francais>. final_answer ne doit jamais être vide.

OUTILS DISPONIBLES : {noms_outils}
RECOMMANDATION DE ROUTAGE (guide non-bloquant) : {trace.routing_hint}

{description_outils}"""

    print(f"\n [Utilisateur] : {ticket_utilisateur}")
    memoire.add_message("user", ticket_utilisateur)
    messages_a_envoyer = [{"role": "system", "content": system_prompt}, *memoire.get_messages()]

    appels_deja_faits: set[tuple[str, str]] = set()
    final_answer = ""
    timed_out = True
    fallback_used = False
    tool_synthesized = False
    guardrail_used = False

    if force_initial_tool and outils_effectifs:
        tool_name = trace.routing_hint.get("outil_recommande")
        argument = trace.routing_hint.get("argument_recommande")
        if isinstance(tool_name, str) and tool_name and isinstance(argument, str) and argument.strip():
            trace.forced_initial_tool = True
            _execute_and_record_tool_call(
                etape=0,
                tool_name=tool_name,
                argument=argument,
                outils_map=outils_map,
                noms_outils=noms_outils,
                appels_deja_faits=appels_deja_faits,
                trace=trace,
                memoire=memoire,
            )
            memoire.add_message(
                "user",
                "Tu dois maintenant exploiter ce résultat d'outil pour produire une réponse finale concrète. "
                "Si une information manque, donne les étapes de diagnostic et d'escalade.",
            )
            messages_a_envoyer = [{"role": "system", "content": system_prompt}, *memoire.get_messages()]
            if deterministic_tool_answer:
                synthesized = _synthesize_answer_from_tools(ticket_utilisateur, trace)
                if synthesized:
                    final_answer = synthesized
                    timed_out = False
                    tool_synthesized = True
                    memoire.add_message("assistant", final_answer)
                    print(f"\n[Agent (Réponse outil structurée)] :\n{final_answer}")

    for etape in range(1, max_iterations + 1):
        if final_answer:
            break
        llm_start = time.perf_counter()
        try:
            decision: AgentDecision = _call_llm(client, modele, messages_a_envoyer, AgentDecision)
        except Exception as exc:
            llm_duration_ms = int((time.perf_counter() - llm_start) * 1000)
            trace.llm_turns.append(LLMTurnTrace(
                etape=etape,
                duree_ms=llm_duration_ms,
                prompt_tokens=None,
                completion_tokens=None,
                action_detectee=False,
                reponse_preview=f"llm_error: {_preview(exc)}",
            ))
            synthesized = _synthesize_answer_from_tools(ticket_utilisateur, trace) if deterministic_tool_answer else ""
            if synthesized:
                final_answer = synthesized
                tool_synthesized = True
                print(f"\n[Agent (Réponse outil après erreur LLM)] :\n{final_answer}")
            else:
                final_answer = _fallback_final_answer(ticket_utilisateur, trace, timed_out=True)
                fallback_used = True
                print(f"\n[Agent (Fallback après erreur LLM)] :\n{final_answer}")
            timed_out = False
            break
        llm_duration_ms = int((time.perf_counter() - llm_start) * 1000)
        prompt_tokens, completion_tokens = _get_decision_usage(decision)

        trace.llm_turns.append(LLMTurnTrace(
            etape=etape,
            duree_ms=llm_duration_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            action_detectee=decision.tool is not None,
            reponse_preview=_preview(decision.model_dump()),
        ))

        if decision.tool is None:
            final_answer = (decision.final_answer or "").strip()
            if not final_answer:
                if etape < max_iterations:
                    trace.empty_answer_repair_count += 1
                    repair_msg = (
                        "Ta réponse finale est vide. Rédige maintenant une réponse finale utile en français. "
                        "N'appelle pas d'autre outil sauf nécessité absolue."
                    )
                    print(" [Agent] Réponse finale vide refusée, demande de réparation au modèle.")
                    memoire.add_message("assistant", "[réponse finale vide]")
                    memoire.add_message("user", repair_msg)
                    messages_a_envoyer = [{"role": "system", "content": system_prompt}, *memoire.get_messages()]
                    continue
                synthesized = _synthesize_answer_from_tools(ticket_utilisateur, trace) if deterministic_tool_answer else ""
                if synthesized:
                    final_answer = synthesized
                    tool_synthesized = True
                    print(f"\n[Agent (Réponse outil après réponse vide)] :\n{final_answer}")
                else:
                    final_answer = _fallback_final_answer(ticket_utilisateur, trace, timed_out=False)
                    fallback_used = True
                    print(f"\n[Agent (Fallback réponse vide)] :\n{final_answer}")
            else:
                synthesized = _synthesize_answer_from_tools(ticket_utilisateur, trace) if deterministic_tool_answer else ""
                if synthesized and not _answer_is_grounded_in_tools(final_answer, trace):
                    final_answer = synthesized
                    guardrail_used = True
                    print(f"\n[Agent (Réponse remplacée par synthèse outil)] :\n{final_answer}")
                else:
                    print(f"\n[Agent (Réponse Finale)] :\n{final_answer}")
            timed_out = False
            memoire.add_message("assistant", final_answer)
            break

        tool_name = decision.tool
        argument = decision.argument or ""
        _execute_and_record_tool_call(
            etape=etape,
            tool_name=tool_name,
            argument=argument,
            outils_map=outils_map,
            noms_outils=noms_outils,
            appels_deja_faits=appels_deja_faits,
            trace=trace,
            memoire=memoire,
        )
        messages_a_envoyer = [{"role": "system", "content": system_prompt}, *memoire.get_messages()]

    if timed_out:
        synthesized = _synthesize_answer_from_tools(ticket_utilisateur, trace) if deterministic_tool_answer else ""
        if synthesized:
            final_answer = synthesized
            timed_out = False
            tool_synthesized = True
            print(f"\n[Agent (Timeout récupéré par synthèse outil)] : {final_answer}")
        else:
            final_answer = _fallback_final_answer(ticket_utilisateur, trace, timed_out=True)
            fallback_used = True
            print(f"\n[Agent (Timeout fallback)] : {final_answer}")

    trace.ended_at_utc = _now_utc_iso()
    trace.total_duree_ms = int((time.perf_counter() - start) * 1000)
    trace.final_answer = final_answer
    trace.structured_answer = _build_structured_answer(final_answer, trace, timed_out=timed_out)
    if tool_synthesized:
        trace.outcome = "tool_synthesized"
    elif guardrail_used:
        trace.outcome = "tool_guardrail_synthesized"
    elif timed_out and fallback_used:
        trace.outcome = "timeout_fallback"
    elif fallback_used:
        trace.outcome = "fallback"
    else:
        trace.outcome = "completed"

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
    modele: str = DEFAULT_AGENT_MODEL,
    modele_provider: str = DEFAULT_AGENT_PROVIDER,
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
            modele_provider=modele_provider,
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
        "provider": modele_provider,
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
