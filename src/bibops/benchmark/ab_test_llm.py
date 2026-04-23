"""
Test A/B automatique : compare deux modeles via la Copilot API (proxy local).

Usage (PowerShell):
    npx copilot-api@latest start
    python src/bibops/benchmark/ab_test_llm.py

Le script lit les tickets depuis tickets_scenario_1.csv, genere une reponse
par modele, puis demande a un modele juge de choisir la meilleure reponse.
Le jugement se fait en une seule passe pour privilegier la rapidite.
"""

import argparse
import csv
import json
import os
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any, Dict, Optional, Tuple

from openai import OpenAI

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
INPUT_CSV = os.path.join(BASE_DIR, "data", "raw", "benchmark", "tickets_scenario_1.csv")
OUTPUT_JSON = os.path.join(BASE_DIR, "data", "outputs", "benchmark", "ab_llm_resultat.json")

COPILOT_BASE_URL = os.environ.get("COPILOT_API_URL", "http://localhost:4141/v1")
DEFAULT_MODEL_A = "gpt-4o-mini"
DEFAULT_MODEL_B = "claude-haiku-4.5"
DEFAULT_JUDGE_MODEL = "gpt-4o"
RANDOM_SEED = 42
MODEL_REQUEST_TIMEOUT_S = 30
JUDGE_REQUEST_TIMEOUT_S = 30
MAX_TICKETS = 10
INTER_TICKET_DELAY_S = 20

# Modeles de secours pour continuer le benchmark en cas d'indisponibilite ponctuelle.
MODEL_FALLBACK_POOL = [
    "gpt-4o-mini",
    "claude-haiku-4.5",
    "gpt-4o",
]

JUDGE_SYSTEM_PROMPT = (
    "Tu es un evaluateur impartial de reponses de support IT. "
    "Tu dois choisir la meilleure reponse entre A et B selon des criteres precis : "
    "pertinence, clarte, actionabilite, et adaptation au contexte. "
    "Retourne uniquement un JSON valide sans texte additionnel."
)


def charger_copilot_api_key() -> str:
    # Le proxy Copilot local n'exige en general pas de clé ; OpenAI SDK en demande une.
    # On accepte une clé explicite via env, sinon on utilise un placeholder.
    key = os.environ.get("COPILOT_API_KEY", "").strip()
    if key:
        return key
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if key:
        return key
    return "copilot"


def _extraire_texte(message: Any) -> str:
    content = getattr(message, "content", None)
    if isinstance(content, str) and content.strip():
        return content.strip()

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
        if parts:
            return "\n".join(parts)

    reasoning = getattr(message, "reasoning", None)
    if isinstance(reasoning, str) and reasoning.strip():
        return reasoning.strip()

    return "[Reponse vide]"


def _executer_avec_timeout(fn, timeout_s: int):
    # Hard timeout côté client pour éviter tout blocage silencieux.
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(fn)
        return future.result(timeout=timeout_s)


def appeler_modele(client: OpenAI, modele: str, contexte: str, ticket: str) -> str:
    try:
        def _call():
            return client.chat.completions.create(
                model=modele,
                messages=[
                    {"role": "system", "content": contexte},
                    {"role": "user", "content": ticket},
                ],
                max_tokens=180,
                temperature=0,
                timeout=MODEL_REQUEST_TIMEOUT_S,
            )

        reponse = _executer_avec_timeout(_call, MODEL_REQUEST_TIMEOUT_S + 1)
        return _extraire_texte(reponse.choices[0].message)
    except FuturesTimeoutError:
        return f"[ERREUR_MODELE {modele}] Delai depasse ({MODEL_REQUEST_TIMEOUT_S}s)."
    except Exception as exc:
        # Certains providers (ex: Gemma via Google AI Studio) refusent les instructions
        # en role 'system'. On retente alors avec un seul message user.
        msg = str(exc)
        if "Developer instruction is not enabled" in msg:
            try:
                def _call_user_only():
                    return client.chat.completions.create(
                        model=modele,
                        messages=[
                            {
                                "role": "user",
                                "content": (
                                    f"Contexte metier: {contexte}\n\n"
                                    f"Question utilisateur: {ticket}\n\n"
                                    "Reponds de facon concise et actionnable."
                                ),
                            }
                        ],
                        max_tokens=180,
                        temperature=0,
                        timeout=MODEL_REQUEST_TIMEOUT_S,
                    )

                reponse = _executer_avec_timeout(_call_user_only, MODEL_REQUEST_TIMEOUT_S + 1)
                return _extraire_texte(reponse.choices[0].message)
            except FuturesTimeoutError:
                return f"[ERREUR_MODELE {modele}] Delai depasse ({MODEL_REQUEST_TIMEOUT_S}s)."
            except Exception as exc2:
                return f"[ERREUR_MODELE {modele}] {exc2}"

        return f"[ERREUR_MODELE {modele}] {exc}"


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
    motifs = [
        "rate limit",
        "temporarily rate-limited",
        "free-models-per-day",
        "no endpoints found",
        "timeout",
        "developer instruction is not enabled",
    ]
    return any(m in t for m in motifs)


def generer_reponse_avec_fallback(
    client: OpenAI,
    modele_initial: str,
    contexte: str,
    ticket: str,
    modeles_interdits: Optional[set[str]] = None,
    etiquette: str = "",
) -> Tuple[str, str, list[str]]:
    interdits = modeles_interdits or set()
    essayes = []

    def _try(modele: str) -> str:
        nonlocal essayes
        essayes.append(modele)
        return appeler_modele(client, modele, contexte, ticket)

    # Si le modele initial est interdit (ex: deja utilise par l'autre bras A/B),
    # on ne le tente pas pour eviter de comparer un modele contre lui-meme.
    if modele_initial not in interdits:
        rep = _try(modele_initial)
        if not _est_reponse_erreur(rep):
            return rep, modele_initial, essayes

        prefix = f"[{etiquette}] " if etiquette else ""
        print(f"     {prefix}echec {modele_initial}: {_message_erreur_court(rep)}")

        if not _erreur_modele_eligible_fallback(rep):
            return rep, modele_initial, essayes
    else:
        rep = f"[ERREUR_MODELE {modele_initial}] Modele interdit pour ce duel A/B."
        prefix = f"[{etiquette}] " if etiquette else ""
        print(f"     {prefix}skip {modele_initial}: modele interdit pour ce ticket")

    for modele in MODEL_FALLBACK_POOL:
        if modele == modele_initial or modele in interdits or modele in essayes:
            continue
        prefix = f"[{etiquette}] " if etiquette else ""
        print(f"     {prefix}fallback -> {modele}")
        rep_fb = _try(modele)
        if not _est_reponse_erreur(rep_fb):
            return rep_fb, modele, essayes
        print(f"     {prefix}echec {modele}: {_message_erreur_court(rep_fb)}")

    return f"{rep} | modeles_tentes={essayes}", modele_initial, essayes


def _construire_prompt_juge(contexte: str, question: str, reponse_a: str, reponse_b: str) -> str:
    return (
        "Contexte metier:\n"
        f"{contexte}\n\n"
        "Question utilisateur:\n"
        f"{question}\n\n"
        "Reponse A:\n"
        f"{reponse_a}\n\n"
        "Reponse B:\n"
        f"{reponse_b}\n\n"
        "Choisis la meilleure reponse (A ou B). "
        "Tu dois favoriser la reponse la plus pertinente, claire, actionnable et adaptee au contexte utilisateur.\n"
        "Retour attendu (JSON strict):\n"
        "{\n"
        '  "choix": "A" ou "B",\n'
        '  "justification": "1-2 phrases"\n'
        "}"
    )


def _extraire_json_depuis_texte(texte: str) -> Optional[Dict[str, Any]]:
    brut = texte.strip()
    try:
        obj = json.loads(brut)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    # Cas frequents: JSON dans un bloc markdown ```json ... ```
    blocs = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", brut, flags=re.DOTALL | re.IGNORECASE)
    for bloc in blocs:
        try:
            obj = json.loads(bloc)
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue

    # Fallback: tente de parser le premier objet JSON trouve dans le texte libre.
    candidats = re.findall(r"\{[\s\S]*?\}", brut)
    for c in candidats:
        try:
            obj = json.loads(c)
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue

    return None


def _normaliser_choix(choix: Any) -> Optional[str]:
    if not isinstance(choix, str):
        return None
    c = choix.strip().upper()
    if c in ("A", "B"):
        return c
    return None


def appeler_juge(
    client: OpenAI,
    modele_juge: str,
    prompt_juge: str,
) -> Tuple[Optional[Dict[str, Any]], str]:
    try:
        def _call(messages, max_tokens: int):
            return client.chat.completions.create(
                model=modele_juge,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0,
                timeout=JUDGE_REQUEST_TIMEOUT_S,
            )

        messages = [
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": prompt_juge},
        ]

        reponse = _executer_avec_timeout(
            lambda: _call(messages, 180), JUDGE_REQUEST_TIMEOUT_S + 1
        )
        texte = _extraire_texte(reponse.choices[0].message)
        obj = _extraire_json_depuis_texte(texte)
        if obj is None:
            # Retry unique avec instruction de format plus stricte.
            strict_prompt = (
                prompt_juge
                + "\n\nIMPORTANT: Retourne UNIQUEMENT un JSON valide en une ligne, "
                + 'exactement {"choix":"A|B","justification":"..."}.'
            )
            reponse2 = _executer_avec_timeout(
                lambda: _call([{"role": "user", "content": strict_prompt}], 140),
                JUDGE_REQUEST_TIMEOUT_S + 1,
            )
            texte2 = _extraire_texte(reponse2.choices[0].message)
            obj = _extraire_json_depuis_texte(texte2)
            if obj is None:
                return None, "JSON invalide"

        choix = _normaliser_choix(obj.get("choix"))
        if choix is None:
            return None, "Champ choix invalide"

        justification = obj.get("justification", "")

        return (
            {
                "choix": choix,
                "justification": str(justification),
            },
            "",
        )
    except FuturesTimeoutError:
        return None, f"Timeout local depasse ({JUDGE_REQUEST_TIMEOUT_S}s)"
    except Exception as exc:
        return None, str(exc)


def appeler_juge_qwen_robuste(
    client: OpenAI,
    modele_juge: str,
    prompt_juge: str,
    modeles_interdits: Optional[set[str]] = None,
) -> Tuple[Optional[Dict[str, Any]], str, str]:
    # Strategie de jugement robuste (Copilot): modele principal puis fallbacks.
    interdits = modeles_interdits or set()
    candidats = [
        modele_juge,
        "gpt-4o",
        "claude-haiku-4.5",
        "gpt-4o-mini",
    ]

    vus = set()
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

    return None, "", "Aucun endpoint juge disponible (gpt-4o/claude-haiku-4.5/gpt-4o-mini): " + " | ".join(erreurs)


def evaluer_ticket_avec_juge_robuste(
    client: OpenAI,
    modele_juge: str,
    contexte: str,
    question: str,
    reponse_a: str,
    reponse_b: str,
    modeles_interdits: Optional[set[str]] = None,
) -> Dict[str, Any]:
    prompt = _construire_prompt_juge(contexte, question, reponse_a, reponse_b)
    res, juge_utilise, err = appeler_juge_qwen_robuste(
        client,
        modele_juge,
        prompt,
        modeles_interdits=modeles_interdits,
    )
    if res is None:
        return {
            "ok": False,
            "erreur": err,
            "choix": "",
            "justification": "",
            "juge_utilise": "",
        }

    return {
        "ok": True,
        "erreur": "",
        "choix": res["choix"],
        "justification": res["justification"],
        "juge_utilise": juge_utilise,
    }


def evaluer_ticket_avec_juge_simple(
    client: OpenAI,
    modele_juge: str,
    contexte: str,
    question: str,
    reponse_a: str,
    reponse_b: str,
) -> Dict[str, Any]:
    prompt = _construire_prompt_juge(contexte, question, reponse_a, reponse_b)
    res, err = appeler_juge(client, modele_juge, prompt)
    if res is None:
        return {
            "ok": False,
            "erreur": err,
            "choix": "",
            "justification": "",
            "juge_utilise": "",
        }

    return {
        "ok": True,
        "erreur": "",
        "choix": res["choix"],
        "justification": res["justification"],
        "juge_utilise": modele_juge,
    }


def evaluer_ticket_par_juge(
    client: OpenAI,
    modele_juge: str,
    contexte: str,
    question: str,
    reponse_a: str,
    reponse_b: str,
    modeles_interdits: Optional[set[str]] = None,
) -> Dict[str, Any]:
    return evaluer_ticket_avec_juge_robuste(
        client=client,
        modele_juge=modele_juge,
        contexte=contexte,
        question=question,
        reponse_a=reponse_a,
        reponse_b=reponse_b,
        modeles_interdits=modeles_interdits,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test A/B automatique (LLM juge) via Copilot API"
    )
    parser.add_argument("--model-a", default=DEFAULT_MODEL_A, help="Premier modele")
    parser.add_argument("--model-b", default=DEFAULT_MODEL_B, help="Deuxieme modele")
    parser.add_argument(
        "--judge-model",
        default=DEFAULT_JUDGE_MODEL,
        help="Modele juge principal",
    )
    parser.add_argument(
        "--output",
        default=OUTPUT_JSON,
        help="Chemin du JSON de resultats",
    )
    parser.add_argument(
        "--inter-ticket-delay",
        type=int,
        default=INTER_TICKET_DELAY_S,
        help="Delai en secondes entre deux tickets (anti rate-limit)",
    )
    args = parser.parse_args()

    api_key = charger_copilot_api_key()
    # Fail fast: OpenAI SDK retries can multiply wait time unexpectedly.
    client = OpenAI(api_key=api_key, base_url=COPILOT_BASE_URL, timeout=20, max_retries=0)
    rng = random.Random(RANDOM_SEED)

    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        tickets = list(csv.DictReader(f))
        if MAX_TICKETS > 0:
            tickets = tickets[:MAX_TICKETS]

    resultats = []
    scores = {args.model_a: 0, args.model_b: 0}

    print(
        f"\n=== Evaluation A/B LLM Judge : {args.model_a} vs {args.model_b} ==="
    )
    print(f"Juge principal : {args.judge_model}")
    print(f"{len(tickets)} ticket(s) a evaluer.\n")

    for idx, ticket in enumerate(tickets):
        tid = ticket["id"]
        contexte = ticket["contexte"]
        question = ticket["ticket"]

        print(f"--- Ticket #{tid} ---")
        print(f"Question : {question}\n")
        print("Generation des reponses en cours...")

        print(f"  -> Appel modele A: {args.model_a}")
        t0 = time.perf_counter()
        rep_modele_a, modele_a_effectif, essais_a = generer_reponse_avec_fallback(
            client,
            args.model_a,
            contexte,
            question,
            modeles_interdits={args.judge_model},
            etiquette="A",
        )
        print(f"     termine en {time.perf_counter() - t0:.1f}s")
        if modele_a_effectif != args.model_a:
            print(f"     fallback A: {args.model_a} -> {modele_a_effectif}")

        print(f"  -> Appel modele B: {args.model_b}")
        t0 = time.perf_counter()
        rep_modele_b, modele_b_effectif, essais_b = generer_reponse_avec_fallback(
            client,
            args.model_b,
            contexte,
            question,
            modeles_interdits={modele_a_effectif, args.judge_model},
            etiquette="B",
        )
        print(f"     termine en {time.perf_counter() - t0:.1f}s")
        if modele_b_effectif != args.model_b:
            print(f"     fallback B: {args.model_b} -> {modele_b_effectif}")

        # Blindage: ordre aleatoire avant passage au juge.
        if rng.random() < 0.5:
            label_a, rep_a = modele_a_effectif, rep_modele_a
            label_b, rep_b = modele_b_effectif, rep_modele_b
        else:
            label_a, rep_a = modele_b_effectif, rep_modele_b
            label_b, rep_b = modele_a_effectif, rep_modele_a

        print("Evaluation par le juge LLM...")
        juge_utilise_ticket = ""
        if _est_reponse_erreur(rep_a) or _est_reponse_erreur(rep_b):
            choix_llm = "?"
            meilleur_modele = "[INDETERMINE]"
            justification_juge = "Comparaison impossible: au moins un modele n'a pas repondu correctement."
            print("[ERREUR_MODELE] Impossible de comparer ce ticket: au moins un modele a renvoye une erreur.")
            if _est_reponse_erreur(rep_a):
                print(f"  A ({label_a}): {_message_erreur_court(rep_a)}")
            if _est_reponse_erreur(rep_b):
                print(f"  B ({label_b}): {_message_erreur_court(rep_b)}")

            # Si le quota free est atteint, continuer ticket par ticket ne sert plus a rien.
            if _est_quota_free_epuise(rep_a) or _est_quota_free_epuise(rep_b):
                print("\n[ARRET] Quota free journalier atteint. Le benchmark est interrompu pour eviter du temps perdu.")
                break
        else:
            jugement = evaluer_ticket_par_juge(
                client=client,
                modele_juge=args.judge_model,
                contexte=contexte,
                question=question,
                reponse_a=rep_a,
                reponse_b=rep_b,
                modeles_interdits={label_a, label_b},
            )

            if not jugement.get("ok"):
                err = jugement.get("erreur", "Erreur inconnue")
                print(f"[ERREUR_JUGE] {err}")
                meilleur_modele = "[INDETERMINE]"
                choix_llm = "?"
                justification_juge = ""
                juge_utilise_ticket = ""
            else:
                choix_llm = jugement["choix"]
                meilleur_modele = label_a if choix_llm == "A" else label_b
                justification_juge = jugement["justification"]
                if meilleur_modele not in scores:
                    scores[meilleur_modele] = 0
                scores[meilleur_modele] += 1
                juge_actif = jugement.get("juge_utilise", args.judge_model)
                juge_utilise_ticket = juge_actif
                if juge_actif != args.judge_model:
                    print(f"     fallback juge: {args.judge_model} -> {juge_actif}")
                print(
                    f"-> Choix juge: {choix_llm} | Meilleur modele: {meilleur_modele} | Juge utilise: {juge_actif}"
                )

        resultats.append(
            {
                "ticket_id": tid,
                "question": question,
                "choix_llm": choix_llm,
                "meilleur_modele": meilleur_modele,
                "juge_utilise": juge_utilise_ticket,
                "justification_juge": justification_juge,
            }
        )

        print()
        if idx < len(tickets) - 1 and args.inter_ticket_delay > 0:
            time.sleep(args.inter_ticket_delay)

    print("=== Synthese des votes ===")
    total_votes = sum(scores.values())
    pourcentages: Dict[str, float] = {}

    for modele, score in scores.items():
        pct = round((score / total_votes) * 100, 1) if total_votes else 0.0
        pourcentages[modele] = pct
        print(f"  {modele} : {score} vote(s) ({pct:.1f}%)")

    payload = {
        "modeles": [args.model_a, args.model_b],
        "juge": args.judge_model,
        "scores": scores,
        "pourcentages": pourcentages,
        "details": resultats,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"\nResultats sauvegardes dans {args.output}")


if __name__ == "__main__":
    main()
