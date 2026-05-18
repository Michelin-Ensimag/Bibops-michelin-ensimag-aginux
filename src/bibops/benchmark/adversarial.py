"""
Boucle d'entraînement adversariale GAN-inspirée pour l'agent BibOps.

  Générateur    = maestro.lancer_agent (mode='react') ou appel LLM direct (mode='zero_shot')
  Discriminateur = DiscriminatorLLM    (juge RAGAS-inspired avec 3 métriques)

Logique par itération :
  1. Le générateur produit une réponse au ticket.
  2. Le Discriminateur évalue 3 métriques : faithfulness, relevance, context.
  3. is_perfect (moyenne >= 7) → succès, la boucle s'arrête.
  4. Sinon, un feedback ciblé par métrique est injecté dans le contexte
     de l'agent pour la prochaine tentative.
  5. Jusqu'à max_iterations.

Rapport final : métriques RAGAS + bilan FinOps (latence, tokens, coût USD).

Exécution directe (démo single-ticket) :
    PYTHONPATH=. python -m src.bibops.benchmark.adversarial
"""
from __future__ import annotations

import signal
import textwrap
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Literal

from src.agent.maestro import lancer_agent
from src.agent.tools import (
    chercher_dans_kb,
    chercher_documentation_technique,
    verifier_statut_serveur,
)
from src.bibops.evaluation.judges.discriminator import DiscriminatorLLM
from src.common.llm_clients import get_copilot_client

GeneratorMode = Literal["react", "zero_shot"]

# Tarification FinOps (USD / 1M tokens) — grille GPT-4o / Claude 3.5 Sonnet.
_PRIX_INPUT_PER_M_USD = 2.50
_PRIX_OUTPUT_PER_M_USD = 10.00

# Couleurs ANSI
C = {
    "r": "\033[0m", "b": "\033[1m", "dim": "\033[2m",
    "red": "\033[91m", "green": "\033[92m", "yellow": "\033[93m",
    "magenta": "\033[95m", "cyan": "\033[96m", "white": "\033[97m",
    "gold": "\033[33m",
}


def _run_zero_shot_generator(
    contexte: str, ticket: str, modele: str,
    temperature: float = 0.3, timeout_s: int = 60,
) -> str:
    """Générateur sans couche agentique : un seul appel LLM, aucun outil, aucune trace."""
    client = get_copilot_client()
    system = (
        f"Tu es un agent IA de support IT Michelin. Contexte : {contexte}\n\n"
        "Réponds directement au ticket de l'utilisateur en français, en proposant "
        "un diagnostic puis des étapes d'action concrètes. Tu n'as accès à aucun outil "
        "externe : utilise uniquement ton raisonnement et le contexte fourni."
    )
    response = client.chat.completions.create(
        model=modele,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": ticket}],
        temperature=temperature, timeout=timeout_s,
    )
    return (response.choices[0].message.content or "").strip()


# ── Console helpers ───────────────────────────────────────────────────────────

def _banner(title: str, color: str, width: int = 68) -> str:
    bar, pad = "═" * width, width - 2
    return f"\n{color}{C['b']}╔{bar}╗\n║  {title:<{pad}}║\n╚{bar}╝{C['r']}"


def _header(label: str, color: str) -> str:
    return f"\n{color}{C['b']}▶ {label}{C['r']}"


def _wrap(text: str, width: int = 76, indent: str = "  ") -> str:
    return textwrap.fill(text, width=width, initial_indent=indent, subsequent_indent=indent)


def _metric_bar(label: str, emoji: str, score: int, width: int = 10) -> str:
    filled, empty = "█" * score, "░" * (width - score)
    color = C["green"] if score >= 8 else (C["yellow"] if score >= 5 else C["red"])
    return f"  {emoji} {label:<14}: {color}[{filled}{empty}] {score}/10{C['r']}"


def _score_color(s: int) -> str:
    return (C["green"] if s >= 8 else C["yellow"] if s >= 5 else C["red"]) + str(s) + C["r"]


# ── FinOps ────────────────────────────────────────────────────────────────────

def _finops_summary(pt: int, ct: int) -> tuple[float, str]:
    """Retourne (cout_usd, commentaire_rentabilite) pour une paire (in, out) tokens."""
    cost = pt / 1_000_000 * _PRIX_INPUT_PER_M_USD + ct / 1_000_000 * _PRIX_OUTPUT_PER_M_USD
    if cost < 0.001:
        comment = "Coût quasi-nul — rentable dès le 1er ticket résolu sans technicien N2."
    elif cost < 0.01:
        comment = "Dérisoire — 1 000 évaluations complètes pour moins d'un café."
    elif cost < 0.10:
        comment = "Économique — ROI positif dès le 2ème ticket N2 évité (~50€/h)."
    else:
        comment = "Coût non négligeable — envisagez un modèle plus léger pour le Discriminateur."
    return cost, comment


# ── Structures de données ─────────────────────────────────────────────────────

@dataclass
class IterationResult:
    numero: int
    reponse_agent: str
    score_faithfulness: int
    score_relevance: int
    score_context: int
    is_perfect: bool
    feedback: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    tool_calls: list[dict] = field(default_factory=list)

    @property
    def score_moyen(self) -> float:
        return round((self.score_faithfulness + self.score_relevance + self.score_context) / 3, 1)

    @property
    def cout_iteration_usd(self) -> float:
        return _finops_summary(self.prompt_tokens, self.completion_tokens)[0]


@dataclass
class AdversarialReport:
    ticket: str
    rca_ground_truth: str
    iterations: list[IterationResult] = field(default_factory=list)
    succes: bool = False
    iterations_necessaires: int | None = None
    latence_totale_s: float = 0.0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    cout_estime_usd: float = 0.0


# ── Feedback ciblé ────────────────────────────────────────────────────────────

_GUIDANCE = {
    "faithfulness": (
        "Ton score de FIDÉLITÉ est de {s}/10. "
        "Tu as probablement inventé des informations absentes du RCA. "
        "Utilise UNIQUEMENT les résultats retournés par les outils. "
        "N'extrapole rien qui ne soit pas dans la documentation récupérée."
    ),
    "relevance": (
        "Ton score de PERTINENCE est de {s}/10. "
        "Ta réponse ne traite pas directement le problème du ticket. "
        "Identifie précisément la cause racine décrite et propose une solution "
        "directement actionnable pour ce cas précis."
    ),
    "context": (
        "Ton score de CONTEXTE est de {s}/10. "
        "Tu n'as pas ramené la bonne documentation avec tes outils, ou tu n'en "
        "as pas utilisé. Rappelle un outil de recherche avec des mots-clés plus "
        "précis (ex: code d'erreur exact, nom du service, localisation)."
    ),
}


def _feedback_contextualise(sf: int, sr: int, sc: int, feedback_llm: str, iteration: int) -> str:
    scores = {"faithfulness": sf, "relevance": sr, "context": sc}
    weakest = min(scores, key=scores.get)
    return (
        f"[RETOUR DU SUPERVISEUR — Tentative {iteration}]\n"
        f"Métriques : Fidélité={sf}/10 | Pertinence={sr}/10 | Contexte={sc}/10\n\n"
        f"Point critique à corriger : {_GUIDANCE[weakest].format(s=scores[weakest])}\n\n"
        f"Analyse détaillée du Discriminateur :\n{feedback_llm}"
    )


# ── Boucle adversariale ───────────────────────────────────────────────────────

def _safe_evaluate(discriminateur: DiscriminatorLLM, ticket: str, reponse: str,
                   rca: str, verbose: bool) -> dict | None:
    """Wrap discriminator call; return None on failure (already logged if verbose)."""
    try:
        return discriminateur.evaluer(ticket=ticket, reponse_agent=reponse, rca_ground_truth=rca)
    except Exception as exc:
        if verbose:
            print(f"{C['red']}[Erreur Discriminateur] {exc}{C['r']}")
            print(f"{C['yellow']}Vérifiez que le proxy est démarré : npx copilot-api@latest start{C['r']}")
        return None


def run_adversarial_training(
    ticket: str,
    rca_ground_truth: str,
    max_iterations: int = 3,
    modele_agent: str = "phi3:latest",
    modele_discriminateur: str = "gpt-5.2",
    contexte_initial: str = "L'entreprise est Michelin.",
    verbose: bool = True,
    mode: GeneratorMode = "react",
    generator_provider: str = "ollama",
) -> AdversarialReport:
    """Lance la boucle d'entraînement adversariale GAN-inspirée."""
    outils = [verifier_statut_serveur, chercher_documentation_technique, chercher_dans_kb]
    discriminateur = DiscriminatorLLM(modele=modele_discriminateur)
    rapport = AdversarialReport(ticket=ticket, rca_ground_truth=rca_ground_truth)
    t_start = time.perf_counter()
    total_pt = total_ct = 0

    if verbose:
        print(_banner("BOUCLE ADVERSARIALE BIBOPS  —  RAGAS-INSPIRED EVALUATION", C["cyan"]))
        print(f"\n{C['b']}Ticket    :{C['r']} {ticket}")
        print(f"{C['b']}RCA réf.  :{C['r']} {C['dim']}{rca_ground_truth[:100]}…{C['r']}")
        print(
            f"{C['b']}Config    :{C['r']} agent={C['yellow']}{modele_agent}{C['r']}"
            f" ({generator_provider}, mode={mode})"
            f" | discriminateur={C['magenta']}{modele_discriminateur}{C['r']}"
            f" | max_iter={max_iterations}"
        )

    contexte_courant = contexte_initial

    for i in range(1, max_iterations + 1):
        if verbose:
            label_mode = "ReAct + RAG" if mode == "react" else "ZERO-SHOT (no tools)"
            print(_banner(f"ITÉRATION {i}/{max_iterations}  —  GÉNÉRATEUR ({label_mode})", C["yellow"]))

        iter_tool_calls: list[dict] = []
        if mode == "zero_shot":
            reponse = _run_zero_shot_generator(contexte=contexte_courant, ticket=ticket, modele=modele_agent)
            if verbose:
                print(f"\n [Utilisateur] : {ticket}")
                print(f"\n[Agent zero-shot] :\n{reponse}")
        else:
            agent_result = lancer_agent(
                contexte=contexte_courant, ticket_utilisateur=ticket,
                outils_disponibles=outils, modele=modele_agent,
                modele_provider=generator_provider,
                return_trace=True,
            )
            reponse = agent_result["reponse_finale"]
            iter_tool_calls = [
                {"tool": tc["outil"], "argument": tc["argument"], "ok": tc["statut"] == "ok"}
                for tc in agent_result.get("trace", {}).get("tool_calls", [])
            ]

        if verbose:
            print(_header("Réponse de l'agent", C["white"]))
            print(_wrap(reponse))
            print(_header("Discriminateur  —  évaluation RAGAS en cours…", C["magenta"]))

        jugement = _safe_evaluate(discriminateur, ticket, reponse, rca_ground_truth, verbose)
        if jugement is None:
            rapport.iterations.append(IterationResult(
                numero=i, reponse_agent=reponse,
                score_faithfulness=0, score_relevance=0, score_context=0,
                is_perfect=False, feedback="Erreur proxy",
            ))
            break

        sf, sr, sc = jugement["score_faithfulness"], jugement["score_relevance"], jugement["score_context"]
        is_perfect = jugement["is_perfect"]
        feedback_llm = jugement.get("feedback_actionnable", "")
        usage = jugement.get("usage", {"prompt_tokens": 0, "completion_tokens": 0})
        pt, ct = usage["prompt_tokens"], usage["completion_tokens"]
        total_pt += pt
        total_ct += ct

        rapport.iterations.append(IterationResult(
            numero=i, reponse_agent=reponse,
            score_faithfulness=sf, score_relevance=sr, score_context=sc,
            is_perfect=is_perfect, feedback=feedback_llm,
            prompt_tokens=pt, completion_tokens=ct,
            tool_calls=iter_tool_calls,
        ))

        if verbose:
            print(f"\n{C['b']}  📊 Métriques RAGAS :{C['r']}")
            print(_metric_bar("Fidélité", "[F]", sf))
            print(_metric_bar("Pertinence", "[P]", sr))
            print(_metric_bar("Contexte", "[C]", sc))
            verdict = f"{C['green']}{C['b']}✅ PARFAIT{C['r']}" if is_perfect else f"{C['red']}{C['b']}❌ INSUFFISANT{C['r']}"
            print(f"\n  {verdict}")
            if pt or ct:
                cost, _ = _finops_summary(pt, ct)
                print(f"  {C['dim']}🪙 Tokens iter : {pt} in | {ct} out  —  ${cost:.6f}{C['r']}")
            if feedback_llm and not is_perfect:
                print(_header("Feedback actionnable du Discriminateur", C["red"]))
                print(_wrap(feedback_llm))

        if is_perfect:
            rapport.succes = True
            rapport.iterations_necessaires = i
            if verbose:
                print(_banner(f"✅  SUCCÈS à l'itération {i}  —  Les 3 métriques sont >= 8 !", C["green"]))
            break

        if i < max_iterations:
            contexte_courant = f"{contexte_initial}\n\n{_feedback_contextualise(sf, sr, sc, feedback_llm, i)}"
            if verbose:
                print(_header(f"Contexte enrichi avec feedback ciblé → relance itération {i+1}", C["cyan"]))
        elif verbose:
            moyenne = round((sf + sr + sc) / 3, 1)
            print(_banner(
                f"⚠️   MAX ITÉRATIONS ATTEINT  —  F={sf} R={sr} C={sc} (moy={moyenne}, seuil moy ≥ 7)",
                C["red"],
            ))

    rapport.latence_totale_s = round(time.perf_counter() - t_start, 2)
    rapport.total_prompt_tokens = total_pt
    rapport.total_completion_tokens = total_ct
    rapport.cout_estime_usd = _finops_summary(total_pt, total_ct)[0]

    if verbose:
        _afficher_rapport_final(rapport)

    return rapport


# ── Rapport récapitulatif ─────────────────────────────────────────────────────

def _afficher_rapport_final(rapport: AdversarialReport) -> None:
    print(_banner("RAPPORT FINAL  —  BOUCLE ADVERSARIALE", C["cyan"]))

    if rapport.succes:
        statut = f"{C['green']}{C['b']}SUCCÈS en {rapport.iterations_necessaires} itération(s){C['r']}"
    else:
        statut = f"{C['red']}{C['b']}ÉCHEC après {len(rapport.iterations)} itération(s){C['r']}"

    ticket_court = rapport.ticket[:80] + "…" if len(rapport.ticket) > 80 else rapport.ticket
    print(f"\n  Résultat  : {statut}")
    print(f"  Ticket    : {ticket_court}")
    print(f"\n  {C['b']}Progression des scores par itération :{C['r']}")

    for it in rapport.iterations:
        line = (
            f"    Iter {it.numero}  "
            f"📊 Fidélité={_score_color(it.score_faithfulness)}/10  "
            f"🎯 Pertinence={_score_color(it.score_relevance)}/10  "
            f"📚 Contexte={_score_color(it.score_context)}/10  "
            f"(moy: {it.score_moyen})"
        )
        if it.is_perfect:
            suffix = f"  {C['green']}✅{C['r']}"
        elif it.feedback.startswith("Erreur proxy"):
            suffix = f"  {C['red']}⚠ Erreur proxy{C['r']}"
        else:
            suffix = f"  {C['red']}→ recadrage{C['r']}"
        print(line + suffix)

    _, commentaire = _finops_summary(rapport.total_prompt_tokens, rapport.total_completion_tokens)
    total_tokens = rapport.total_prompt_tokens + rapport.total_completion_tokens
    print(_banner("BILAN FINOPS & PERFORMANCES", C["gold"]))
    print(f"\n  ⏱  {C['b']}Latence totale   :{C['r']} {rapport.latence_totale_s:.2f} secondes")
    print(
        f"  🪙  {C['b']}Tokens consommés :{C['r']} "
        f"{rapport.total_prompt_tokens:,} (In) | {rapport.total_completion_tokens:,} (Out)"
        f"  —  {total_tokens:,} total"
    )
    print(f"    {C['b']}Coût estimé      :{C['r']} {C['green']}${rapport.cout_estime_usd:.6f} USD{C['r']}")
    print(f"    {C['b']}Rentabilité      :{C['r']} {C['gold']}{commentaire}{C['r']}")
    print(
        f"\n  {C['dim']}Tarification : ${_PRIX_INPUT_PER_M_USD}/M input"
        f" | ${_PRIX_OUTPUT_PER_M_USD}/M output (GPT-4o / Claude Sonnet 3.5){C['r']}"
    )


# ── Démo single-ticket ────────────────────────────────────────────────────────

_DEMO_TICKET = (
    "Le VPN Cisco me donne l'erreur 412 et je suis en Chine. "
    "J'ai déjà redémarré mon PC et réinstallé AnyConnect mais rien ne change."
)
_DEMO_RCA = (
    "L'erreur 412 'Tunnel rejected by server' en Chine est causée par le "
    "blocage du port UDP 1194 (IPSec/IKEv2) par le Great Firewall of China. "
    "La solution est de reconfigurer AnyConnect pour utiliser le port TCP 443 "
    "(TLS fallback) via le profil VPN 'Michelin-China-Fallback'. "
    "Si ce profil est absent du client, l'utilisateur doit contacter le support "
    "N2 pour que l'équipe réseau active le profil de contournement GFW sur son "
    "compte AnyConnect et lui fournisse le fichier de configuration XML."
)


@contextmanager
def _sigalrm_timeout(seconds: int) -> Iterator[None]:
    if seconds <= 0:
        yield
        return

    def _on_timeout(_signum, _frame):
        raise TimeoutError(f"Timeout adversarial dépassé ({seconds}s).")

    signal.signal(signal.SIGALRM, _on_timeout)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)


def main() -> None:
    """Démo single-ticket de la boucle adversariale (entrée argparse-compatible)."""
    import argparse

    parser = argparse.ArgumentParser(description="Démo single-ticket de la boucle adversariale BibOps.")
    parser.add_argument("--max-iter", type=int, default=2, help="Itérations adversariales (default: 2).")
    parser.add_argument("--mode", choices=["react", "zero_shot"], default="react")
    parser.add_argument("--generator-model", default="gpt-4o-mini")
    parser.add_argument("--generator-provider", choices=["copilot", "ollama"], default="copilot")
    parser.add_argument("--judge-model", default="gpt-4o")
    parser.add_argument("--run-timeout-s", type=int, default=120, help="Timeout SIGALRM global (0 pour désactiver).")
    args = parser.parse_args()

    try:
        with _sigalrm_timeout(args.run_timeout_s):
            run_adversarial_training(
                ticket=_DEMO_TICKET,
                rca_ground_truth=_DEMO_RCA,
                max_iterations=args.max_iter,
                modele_agent=args.generator_model,
                generator_provider=args.generator_provider,
                mode=args.mode,
                modele_discriminateur=args.judge_model,
                contexte_initial="L'entreprise est Michelin. Le VPN principal est Cisco AnyConnect.",
            )
    except TimeoutError as exc:
        print(f"\n[WARN] {exc}")
        print("[WARN] Arrêt propre de la démo adversariale.")


if __name__ == "__main__":
    main()
