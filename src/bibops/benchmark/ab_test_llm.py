"""
Test A/B automatique : compare deux modeles via la Copilot API (proxy local).

Usage:
    npx copilot-api@latest start
    bibops bench ab-test --mode llm

Le script lit les tickets depuis tickets_scenario_1.csv, genere une reponse
par modele, puis demande a un modele juge de choisir la meilleure reponse.
"""

import argparse
import csv
import json
import os
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Any

from openai import OpenAI

from src.common.config import BASE_DIR as PROJECT_ROOT
from src.common.config import OUTPUT_DIR, validate_judge_model
from src.common.config import DEFAULT_JUDGE_MODEL as CONFIG_DEFAULT_JUDGE_MODEL
from src.common.config import INPUT_CSV as DEFAULT_INPUT_CSV
from src.common.config import MODEL_REQUEST_TIMEOUT_S
from src.common.llm_clients import get_copilot_client
from src.common.text import _extraire_texte

BASE_DIR = str(PROJECT_ROOT)
INPUT_CSV = str(DEFAULT_INPUT_CSV)
OUTPUT_JSON = str(OUTPUT_DIR / "ab_llm_resultat.json")

DEFAULT_MODEL_A = "gpt-4o-mini"
DEFAULT_MODEL_B = "claude-haiku-4.5"
DEFAULT_JUDGE_MODEL = CONFIG_DEFAULT_JUDGE_MODEL
RANDOM_SEED = 42
JUDGE_REQUEST_TIMEOUT_S = 30
MAX_TICKETS = 3
INTER_TICKET_DELAY_S = 0

MODEL_FALLBACK_POOL = ["gpt-4o-mini", "claude-haiku-4.5", "gpt-4o"]

JUDGE_SYSTEM_PROMPT = (
    "Tu es un evaluateur impartial de reponses de support IT. "
    "Tu dois choisir la meilleure reponse entre A et B selon des criteres precis : "
    "pertinence, clarte, actionabilite, et adaptation au contexte. "
    "Retourne uniquement un JSON valide sans texte additionnel."
)

# ---------------------------------------------------------------------------
# Helpers (previously in src/common/text — only used by this A/B pipeline)
# ---------------------------------------------------------------------------

def _executer_avec_timeout(fn, timeout_s: int):
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(fn).result(timeout=timeout_s)


def _extraire_json_depuis_texte(texte: str) -> dict | None:
    brut = texte.strip()
    try:
        obj = json.loads(brut)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    for bloc in re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", brut, flags=re.DOTALL | re.IGNORECASE):
        try:
            obj = json.loads(bloc)
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue
    for c in re.findall(r"\{[\s\S]*?\}", brut):
        try:
            obj = json.loads(c)
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue
    return None


def _normaliser_choix(choix: Any) -> str | None:
    if not isinstance(choix, str):
        return None
    c = choix.strip().upper()
    return c if c in ("A", "B") else None


def _est_reponse_erreur(texte: str) -> bool:
    return texte.strip().startswith("[ERREUR_MODELE")


def _est_quota_free_epuise(texte: str) -> bool:
    t = texte.lower()
    return "free-models-per-day" in t or "x-ratelimit-remaining': '0" in t


def _message_erreur_court(texte_erreur: str) -> str:
    t = texte_erreur.lower()
    if "free-models-per-day" in t:
        return "Quota OpenRouter free-models-per-day atteint (remaining=0)."
    if "temporarily rate-limited" in t:
        return "Modele temporairement rate-limited par le provider."
    if "no endpoints found" in t:
        return "Aucun endpoint disponible pour ce modele actuellement."
    if "timeout" in t:
        return "Delai depasse pour cet appel modele."
    if "json invalide" in t or "champ choix invalide" in t:
        return "Sortie juge invalide (format JSON non conforme ou tronque)."
    return texte_erreur


def _erreur_modele_eligible_fallback(texte_erreur: str) -> bool:
    t = texte_erreur.lower()
    return any(m in t for m in [
        "rate limit", "temporarily rate-limited", "free-models-per-day",
        "no endpoints found", "timeout", "developer instruction is not enabled",
    ])


def appeler_modele(client: OpenAI, modele: str, contexte: str, ticket: str, timeout_s: int = MODEL_REQUEST_TIMEOUT_S) -> str:
    try:
        def _call():
            return client.chat.completions.create(
                model=modele,
                messages=[{"role": "system", "content": contexte}, {"role": "user", "content": ticket}],
                max_tokens=180,
                temperature=0,
                timeout=timeout_s,
            )
        reponse = _executer_avec_timeout(_call, timeout_s + 1)
        return _extraire_texte(reponse.choices[0].message)
    except FuturesTimeoutError:
        return f"[ERREUR_MODELE {modele}] Delai depasse ({timeout_s}s)."
    except Exception as exc:
        if "Developer instruction is not enabled" in str(exc):
            try:
                def _call_user_only():
                    return client.chat.completions.create(
                        model=modele,
                        messages=[{"role": "user", "content": f"Contexte metier: {contexte}\n\nQuestion utilisateur: {ticket}\n\nReponds de facon concise et actionnable."}],
                        max_tokens=180,
                        temperature=0,
                        timeout=timeout_s,
                    )
                reponse = _executer_avec_timeout(_call_user_only, timeout_s + 1)
                return _extraire_texte(reponse.choices[0].message)
            except Exception as exc2:
                return f"[ERREUR_MODELE {modele}] {exc2}"
        return f"[ERREUR_MODELE {modele}] {exc}"

# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def generer_reponse_avec_fallback(
    client: OpenAI,
    modele_initial: str,
    contexte: str,
    ticket: str,
    modeles_interdits: set[str] | None = None,
    etiquette: str = "",
) -> tuple[str, str, list[str]]:
    interdits = modeles_interdits or set()
    essayes: list[str] = []

    def _try(modele: str) -> str:
        essayes.append(modele)
        return appeler_modele(client, modele, contexte, ticket, MODEL_REQUEST_TIMEOUT_S)

    prefix = f"[{etiquette}] " if etiquette else ""

    if modele_initial not in interdits:
        rep = _try(modele_initial)
        if not _est_reponse_erreur(rep):
            return rep, modele_initial, essayes
        print(f"     {prefix}echec {modele_initial}: {_message_erreur_court(rep)}")
        if not _erreur_modele_eligible_fallback(rep):
            return rep, modele_initial, essayes
    else:
        print(f"     {prefix}skip {modele_initial}: modele interdit pour ce ticket")
        rep = f"[ERREUR_MODELE {modele_initial}] Modele interdit pour ce duel A/B."

    for modele in MODEL_FALLBACK_POOL:
        if modele == modele_initial or modele in interdits or modele in essayes:
            continue
        print(f"     {prefix}fallback -> {modele}")
        rep_fb = _try(modele)
        if not _est_reponse_erreur(rep_fb):
            return rep_fb, modele, essayes
        print(f"     {prefix}echec {modele}: {_message_erreur_court(rep_fb)}")

    return f"{rep} | modeles_tentes={essayes}", modele_initial, essayes


def _construire_prompt_juge(contexte: str, question: str, reponse_a: str, reponse_b: str) -> str:
    return (
        f"Contexte metier:\n{contexte}\n\n"
        f"Question utilisateur:\n{question}\n\n"
        f"Reponse A:\n{reponse_a}\n\n"
        f"Reponse B:\n{reponse_b}\n\n"
        "Choisis la meilleure reponse (A ou B). "
        "Tu dois favoriser la reponse la plus pertinente, claire, actionnable et adaptee au contexte utilisateur.\n"
        'Retour attendu (JSON strict):\n{\n  "choix": "A" ou "B",\n  "justification": "1-2 phrases"\n}'
    )


def appeler_juge(client: OpenAI, modele_juge: str, prompt_juge: str) -> tuple[dict[str, Any] | None, str]:
    try:
        def _call(messages, max_tokens: int):
            return client.chat.completions.create(
                model=modele_juge, messages=messages, max_tokens=max_tokens,
                temperature=0, timeout=JUDGE_REQUEST_TIMEOUT_S,
            )

        messages = [{"role": "system", "content": JUDGE_SYSTEM_PROMPT}, {"role": "user", "content": prompt_juge}]
        reponse = _executer_avec_timeout(lambda: _call(messages, 180), JUDGE_REQUEST_TIMEOUT_S + 1)
        texte = _extraire_texte(reponse.choices[0].message)
        obj = _extraire_json_depuis_texte(texte)

        if obj is None:
            strict_prompt = prompt_juge + '\n\nIMPORTANT: Retourne UNIQUEMENT un JSON valide en une ligne, exactement {"choix":"A|B","justification":"..."}.'
            reponse2 = _executer_avec_timeout(lambda: _call([{"role": "user", "content": strict_prompt}], 140), JUDGE_REQUEST_TIMEOUT_S + 1)
            obj = _extraire_json_depuis_texte(_extraire_texte(reponse2.choices[0].message))
            if obj is None:
                return None, "JSON invalide"

        choix = _normaliser_choix(obj.get("choix"))
        if choix is None:
            return None, "Champ choix invalide"
        return {"choix": choix, "justification": str(obj.get("justification", ""))}, ""
    except FuturesTimeoutError:
        return None, f"Timeout local depasse ({JUDGE_REQUEST_TIMEOUT_S}s)"
    except Exception as exc:
        return None, str(exc)


def appeler_juge_qwen_robuste(
    client: OpenAI,
    modele_juge: str,
    prompt_juge: str,
    modeles_interdits: set[str] | None = None,
) -> tuple[dict[str, Any] | None, str, str]:
    interdits = modeles_interdits or set()
    candidats = [modele_juge, "gpt-4o", "claude-haiku-4.5", "gpt-4o-mini"]
    vus: set[str] = set()
    erreurs: list[str] = []

    for modele in candidats:
        if not modele or modele in vus or modele in interdits:
            if modele in interdits:
                print(f"     [JUGE] skip {modele}: deja utilise comme modele A/B sur ce ticket")
            continue
        vus.add(modele)
        res, err = appeler_juge(client, modele, prompt_juge)
        if res is not None:
            return res, modele, ""
        print(f"     [JUGE] echec {modele}: {_message_erreur_court(err)}")
        erreurs.append(f"{modele}: {_message_erreur_court(err)}")
        print("     [JUGE] bascule vers le fallback suivant...")

    if not erreurs:
        return None, "", "Aucun juge disponible: tous les fallback sont interdits pour ce ticket."
    return None, "", "Aucun endpoint juge disponible: " + " | ".join(erreurs)


def evaluer_ticket_par_juge(
    client: OpenAI,
    modele_juge: str,
    contexte: str,
    question: str,
    reponse_a: str,
    reponse_b: str,
    modeles_interdits: set[str] | None = None,
) -> dict[str, Any]:
    prompt = _construire_prompt_juge(contexte, question, reponse_a, reponse_b)
    res, juge_utilise, err = appeler_juge_qwen_robuste(client, modele_juge, prompt, modeles_interdits=modeles_interdits)
    if res is None:
        return {"ok": False, "erreur": err, "choix": "", "justification": "", "juge_utilise": ""}
    return {"ok": True, "erreur": "", "choix": res["choix"], "justification": res["justification"], "juge_utilise": juge_utilise}


def main() -> None:
    parser = argparse.ArgumentParser(description="Test A/B automatique (LLM juge) via Copilot API")
    parser.add_argument("--model-a", default=DEFAULT_MODEL_A)
    parser.add_argument("--model-b", default=DEFAULT_MODEL_B)
    parser.add_argument("--judge-model", default=DEFAULT_JUDGE_MODEL)
    parser.add_argument("--output", default=OUTPUT_JSON)
    parser.add_argument("--max-tickets", type=int, default=int(os.environ.get("BIBOPS_AB_LLM_MAX_TICKETS", MAX_TICKETS)))
    parser.add_argument("--inter-ticket-delay", type=int, default=int(os.environ.get("BIBOPS_AB_LLM_INTER_TICKET_DELAY", INTER_TICKET_DELAY_S)))
    args = parser.parse_args()
    try:
        validate_judge_model(args.judge_model)
    except ValueError as exc:
        parser.error(str(exc))

    client = get_copilot_client()
    rng = random.Random(RANDOM_SEED)

    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        tickets = list(csv.DictReader(f))[:args.max_tickets] if args.max_tickets > 0 else list(csv.DictReader(f))

    resultats = []
    scores = {args.model_a: 0, args.model_b: 0}

    print(f"\n=== Evaluation A/B LLM Judge : {args.model_a} vs {args.model_b} ===")
    print(f"Juge principal : {args.judge_model}")
    print(f"{len(tickets)} ticket(s) a evaluer.\n")

    for idx, ticket in enumerate(tickets):
        tid, contexte, question = ticket["id"], ticket["contexte"], ticket["ticket"]
        print(f"--- Ticket #{tid} ---\nQuestion : {question}\n")

        print(f"  -> Appel modele A: {args.model_a}")
        t0 = time.perf_counter()
        rep_a, modele_a_eff, _ = generer_reponse_avec_fallback(client, args.model_a, contexte, question, modeles_interdits={args.judge_model}, etiquette="A")
        print(f"     termine en {time.perf_counter() - t0:.1f}s")
        if modele_a_eff != args.model_a:
            print(f"     fallback A: {args.model_a} -> {modele_a_eff}")

        print(f"  -> Appel modele B: {args.model_b}")
        t0 = time.perf_counter()
        rep_b, modele_b_eff, _ = generer_reponse_avec_fallback(client, args.model_b, contexte, question, modeles_interdits={modele_a_eff, args.judge_model}, etiquette="B")
        print(f"     termine en {time.perf_counter() - t0:.1f}s")
        if modele_b_eff != args.model_b:
            print(f"     fallback B: {args.model_b} -> {modele_b_eff}")

        if rng.random() < 0.5:
            label_a, show_a, label_b, show_b = modele_a_eff, rep_a, modele_b_eff, rep_b
        else:
            label_a, show_a, label_b, show_b = modele_b_eff, rep_b, modele_a_eff, rep_a

        choix_llm = "?"
        meilleur_modele = "[INDETERMINE]"
        justification_juge = ""
        juge_utilise_ticket = ""

        print("Evaluation par le juge LLM...")
        if _est_reponse_erreur(show_a) or _est_reponse_erreur(show_b):
            justification_juge = "Comparaison impossible: au moins un modele n'a pas repondu correctement."
            print("[ERREUR_MODELE] Impossible de comparer ce ticket.")
            if _est_quota_free_epuise(show_a) or _est_quota_free_epuise(show_b):
                print("\n[ARRET] Quota free journalier atteint.")
                break
        else:
            jugement = evaluer_ticket_par_juge(client, args.judge_model, contexte, question, show_a, show_b, modeles_interdits={label_a, label_b})
            if not jugement.get("ok"):
                print(f"[ERREUR_JUGE] {jugement.get('erreur', '')}")
            else:
                choix_llm = jugement["choix"]
                meilleur_modele = label_a if choix_llm == "A" else label_b
                justification_juge = jugement["justification"]
                juge_utilise_ticket = jugement.get("juge_utilise", args.judge_model)
                if meilleur_modele not in scores:
                    scores[meilleur_modele] = 0
                scores[meilleur_modele] += 1
                if juge_utilise_ticket != args.judge_model:
                    print(f"     fallback juge: {args.judge_model} -> {juge_utilise_ticket}")
                print(f"-> Choix juge: {choix_llm} | Meilleur: {meilleur_modele} | Juge: {juge_utilise_ticket}")

        resultats.append({"ticket_id": tid, "question": question, "choix_llm": choix_llm, "meilleur_modele": meilleur_modele, "juge_utilise": juge_utilise_ticket, "justification_juge": justification_juge})
        print()
        if idx < len(tickets) - 1 and args.inter_ticket_delay > 0:
            time.sleep(args.inter_ticket_delay)

    total_votes = sum(scores.values())
    pourcentages = {m: round((s / total_votes) * 100, 1) if total_votes else 0.0 for m, s in scores.items()}
    print("=== Synthese des votes ===")
    for modele, score in scores.items():
        print(f"  {modele} : {score} vote(s) ({pourcentages[modele]:.1f}%)")

    payload = {"modeles": [args.model_a, args.model_b], "juge": args.judge_model, "scores": scores, "pourcentages": pourcentages, "details": resultats}
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\nResultats sauvegardes dans {args.output}")


if __name__ == "__main__":
    main()
