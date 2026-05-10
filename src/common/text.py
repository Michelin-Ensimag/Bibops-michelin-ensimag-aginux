"""Shared text processing and API call helpers."""
from __future__ import annotations

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Any

from openai import OpenAI

from src.common.config import MODEL_REQUEST_TIMEOUT_S


def charger_copilot_api_key() -> str:
    for env in ("COPILOT_API_KEY", "OPENAI_API_KEY"):
        key = os.environ.get(env, "").strip()
        if key:
            return key
    return "copilot"


def _extraire_texte(message: Any) -> str:
    content = getattr(message, "content", None)
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        parts = [item.get("text", "").strip() for item in content if isinstance(item, dict) and item.get("text")]
        if parts:
            return "\n".join(parts)
    reasoning = getattr(message, "reasoning", None)
    if isinstance(reasoning, str) and reasoning.strip():
        return reasoning.strip()
    return "[Reponse vide]"


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


def extraire_texte_reponse(reponse_ollama) -> str:
    """Extract response text from Ollama response without assuming a unique format."""
    def _lire(obj, cle):
        return obj.get(cle) if isinstance(obj, dict) else getattr(obj, cle, None)

    message = _lire(reponse_ollama, "message")
    contenu = _lire(message, "content") if message is not None else None
    if isinstance(contenu, str):
        return contenu
    return ""


def extraire_compteurs_tokens(reponse_ollama) -> tuple[int | None, str]:
    """Count tokens via native Ollama metadata, without approximation."""
    def _lire(obj, cle):
        return obj.get(cle) if isinstance(obj, dict) else getattr(obj, cle, None)

    prompt_eval_count = _lire(reponse_ollama, "prompt_eval_count")
    eval_count = _lire(reponse_ollama, "eval_count")
    if isinstance(prompt_eval_count, int) and isinstance(eval_count, int):
        return prompt_eval_count + eval_count, "ollama_native"

    usage = _lire(reponse_ollama, "usage")
    if isinstance(usage, dict):
        total_tokens = usage.get("total_tokens")
        if isinstance(total_tokens, int):
            return total_tokens, "usage_total_tokens"
        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")
        if isinstance(prompt_tokens, int) and isinstance(completion_tokens, int):
            return prompt_tokens + completion_tokens, "usage_prompt_plus_completion"

    return None, "native_tokens_absents"
