"""
src/llm_professor/adversarial_loop.py

Boucle d'entraînement adversariale GAN-inspirée pour l'agent BibOps.

  Générateur    = maestro.lancer_agent  (produit une réponse au ticket)
  Discriminateur = DiscriminatorLLM     (juge RAGAS-inspired avec 3 métriques)

Logique par itération :
  1. lancer_agent génère une réponse.
  2. Le Discriminateur évalue 3 métriques : faithfulness, relevance, context.
  3. is_perfect (les 3 >= 8) → succès, la boucle s'arrête.
  4. Sinon, un feedback ciblé par métrique est injecté dans le contexte
     de l'agent pour la prochaine tentative.
  5. Jusqu'à max_iterations.

Rapport final : métriques RAGAS + bilan FinOps (latence, tokens, coût USD).

Exécution directe (démo) :
    python -m src.llm_professor.adversarial_loop
"""

import os
import sys
import textwrap
import time
from dataclasses import dataclass, field
from typing import List, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.agents.maestro import lancer_agent
from src.agents.outils import (
    chercher_dans_kb,
    chercher_documentation_technique,
    verifier_statut_serveur,
)
from src.llm_professor.discriminator import DiscriminatorLLM


# ── Tarification FinOps (USD / 1M tokens) ────────────────────────────────────
# Grille GPT-4o / Claude 3.5 Sonnet — à ajuster selon le modèle réel utilisé.
_PRIX_INPUT_PER_M_USD  = 2.50
_PRIX_OUTPUT_PER_M_USD = 10.00


# ── Couleurs ANSI ─────────────────────────────────────────────────────────────

_R = "\033[0m"
_B = "\033[1m"
_RED = "\033[91m"
_GREEN = "\033[92m"
_YELLOW = "\033[93m"
_CYAN = "\033[96m"
_MAGENTA = "\033[95m"
_WHITE = "\033[97m"
_DIM = "\033[2m"
_GOLD = "\033[33m"


def _banner(title: str, color: str, width: int = 68) -> str:
    bar = "═" * width
    pad = width - 2
    return f"\n{color}{_B}╔{bar}╗\n║  {title:<{pad}}║\n╚{bar}╝{_R}"


def _header(label: str, color: str) -> str:
    return f"\n{color}{_B}▶ {label}{_R}"


def _wrap(text: str, width: int = 76, indent: str = "  ") -> str:
    return textwrap.fill(
        text, width=width, initial_indent=indent, subsequent_indent=indent
    )


def _metric_bar(label: str, emoji: str, score: int, width: int = 10) -> str:
    """Affiche une barre de progression colorée pour une métrique."""
    filled = "█" * score
    empty = "░" * (width - score)
    color = _GREEN if score >= 8 else (_YELLOW if score >= 5 else _RED)
    return f"  {emoji} {label:<14}: {color}[{filled}{empty}] {score}/10{_R}"


# ── Calcul du coût ─────────────────────────────────────────────────────────────

def _calculer_cout(prompt_tokens: int, completion_tokens: int) -> float:
    """Formule : (input / 1M * 2.50) + (output / 1M * 10.00)."""
    return (prompt_tokens / 1_000_000 * _PRIX_INPUT_PER_M_USD
            + completion_tokens / 1_000_000 * _PRIX_OUTPUT_PER_M_USD)


def _commentaire_rentabilite(cout_usd: float) -> str:
    """Génère un commentaire FinOps contextuel selon le coût total."""
    if cout_usd < 0.001:
        return "Coût quasi-nul — rentable dès le 1er ticket résolu sans technicien N2."
    if cout_usd < 0.01:
        return "Dérisoire — 1 000 évaluations complètes pour moins d'un café."
    if cout_usd < 0.10:
        return "Économique — ROI positif dès le 2ème ticket N2 évité (~50€/h)."
    return "Coût non négligeable — envisagez un modèle plus léger pour le Discriminateur."


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

    @property
    def score_moyen(self) -> float:
        return round((self.score_faithfulness + self.score_relevance + self.score_context) / 3, 1)

    @property
    def cout_iteration_usd(self) -> float:
        return _calculer_cout(self.prompt_tokens, self.completion_tokens)


@dataclass
class AdversarialReport:
    ticket: str
    rca_ground_truth: str
    iterations: List[IterationResult] = field(default_factory=list)
    succes: bool = False
    iterations_necessaires: Optional[int] = None
    # Champs FinOps — remplis par run_adversarial_training en fin de boucle
    latence_totale_s: float = 0.0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    cout_estime_usd: float = 0.0


# ── Construction du feedback ciblé ───────────────────────────────────────────

def _feedback_contextualise(
    sf: int, sr: int, sc: int, feedback_llm: str, iteration: int
) -> str:
    """
    Enrichit le feedback du Discriminateur avec des instructions précises
    basées sur la métrique la plus faible, pour guider l'agent à l'itération suivante.
    """
    scores = {"faithfulness": sf, "relevance": sr, "context": sc}
    metrique_faible = min(scores, key=scores.get)
    score_faible = scores[metrique_faible]

    guidance = {
        "faithfulness": (
            f"Ton score de FIDÉLITÉ est de {score_faible}/10. "
            "Tu as probablement inventé des informations absentes du RCA. "
            "Utilise UNIQUEMENT les résultats retournés par les outils. "
            "N'extrapole rien qui ne soit pas dans la documentation récupérée."
        ),
        "relevance": (
            f"Ton score de PERTINENCE est de {score_faible}/10. "
            "Ta réponse ne traite pas directement le problème du ticket. "
            "Identifie précisément la cause racine décrite et propose une solution "
            "directement actionnable pour ce cas précis."
        ),
        "context": (
            f"Ton score de CONTEXTE est de {score_faible}/10. "
            "Tu n'as pas ramené la bonne documentation avec tes outils, ou tu n'en "
            "as pas utilisé. Rappelle un outil de recherche avec des mots-clés plus "
            "précis (ex: code d'erreur exact, nom du service, localisation)."
        ),
    }

    return (
        f"[RETOUR DU SUPERVISEUR — Tentative {iteration}]\n"
        f"Métriques : Fidélité={sf}/10 | Pertinence={sr}/10 | Contexte={sc}/10\n\n"
        f"Point critique à corriger : {guidance[metrique_faible]}\n\n"
        f"Analyse détaillée du Discriminateur :\n{feedback_llm}"
    )


# ── Boucle adversariale ───────────────────────────────────────────────────────

def run_adversarial_training(
    ticket: str,
    rca_ground_truth: str,
    max_iterations: int = 3,
    modele_agent: str = "phi3:latest",
    modele_discriminateur: str = "gpt-5.2",
    contexte_initial: str = "L'entreprise est Michelin.",
    verbose: bool = True,
) -> AdversarialReport:
    """
    Lance la boucle d'entraînement adversariale GAN-inspirée.

    Args:
        ticket               : Ticket utilisateur à résoudre.
        rca_ground_truth     : Diagnostic parfait (corrigé de référence).
        max_iterations       : Nombre maximum de tentatives de l'agent.
        modele_agent         : Modèle Ollama local pour lancer_agent.
        modele_discriminateur: Modèle pour le Discriminateur (GPT si proxy Copilot).
        contexte_initial     : Contexte d'entreprise passé à lancer_agent.
        verbose              : Active les logs colorés en console.

    Returns:
        AdversarialReport avec l'historique complet + bilan FinOps.
    """
    outils = [verifier_statut_serveur, chercher_documentation_technique, chercher_dans_kb]
    discriminateur = DiscriminatorLLM(modele=modele_discriminateur)
    rapport = AdversarialReport(ticket=ticket, rca_ground_truth=rca_ground_truth)

    # ── Démarrage du chronomètre global ──────────────────────────────────────
    t_start = time.perf_counter()
    total_prompt_tokens = 0
    total_completion_tokens = 0

    if verbose:
        print(_banner("BOUCLE ADVERSARIALE BIBOPS  —  RAGAS-INSPIRED EVALUATION", _CYAN))
        print(f"\n{_B}Ticket    :{_R} {ticket}")
        print(f"{_B}RCA réf.  :{_R} {_DIM}{rca_ground_truth[:100]}…{_R}")
        print(
            f"{_B}Config    :{_R} agent={_YELLOW}{modele_agent}{_R}"
            f" | discriminateur={_MAGENTA}{modele_discriminateur}{_R}"
            f" | max_iter={max_iterations}"
        )

    contexte_courant = contexte_initial

    for i in range(1, max_iterations + 1):

        # ── Étape 1 : Générateur ──────────────────────────────────────────────
        if verbose:
            print(_banner(f"ITÉRATION {i}/{max_iterations}  —  GÉNÉRATEUR (agent)", _YELLOW))

        reponse = lancer_agent(
            contexte=contexte_courant,
            ticket_utilisateur=ticket,
            outils_disponibles=outils,
            modele=modele_agent,
        )

        if verbose:
            print(_header("Réponse de l'agent", _WHITE))
            print(_wrap(reponse))

        # ── Étape 2 : Discriminateur ──────────────────────────────────────────
        if verbose:
            print(_header("Discriminateur  —  évaluation RAGAS en cours…", _MAGENTA))

        try:
            jugement = discriminateur.evaluer(
                ticket=ticket,
                reponse_agent=reponse,
                rca_ground_truth=rca_ground_truth,
            )
        except Exception as exc:
            if verbose:
                print(f"{_RED}[Erreur Discriminateur] {exc}{_R}")
                print(f"{_YELLOW}Vérifiez que le proxy est démarré : npx copilot-api@latest start{_R}")
            rapport.iterations.append(
                IterationResult(
                    numero=i, reponse_agent=reponse,
                    score_faithfulness=0, score_relevance=0, score_context=0,
                    is_perfect=False, feedback=f"Erreur proxy : {exc}",
                )
            )
            break

        sf = jugement["score_faithfulness"]
        sr = jugement["score_relevance"]
        sc = jugement["score_context"]
        is_perfect = jugement["is_perfect"]
        feedback_llm = jugement.get("feedback_actionnable", "")
        usage = jugement.get("usage", {"prompt_tokens": 0, "completion_tokens": 0})

        # Accumulation globale des tokens
        pt = usage["prompt_tokens"]
        ct = usage["completion_tokens"]
        total_prompt_tokens += pt
        total_completion_tokens += ct

        rapport.iterations.append(
            IterationResult(
                numero=i, reponse_agent=reponse,
                score_faithfulness=sf, score_relevance=sr, score_context=sc,
                is_perfect=is_perfect, feedback=feedback_llm,
                prompt_tokens=pt, completion_tokens=ct,
            )
        )

        if verbose:
            print(f"\n{_B}  📊 Métriques RAGAS :{_R}")
            print(_metric_bar("Fidélité",   "[F]", sf))
            print(_metric_bar("Pertinence", "[P]", sr))
            print(_metric_bar("Contexte",   "[C]", sc))
            verdict = f"{_GREEN}{_B}✅ PARFAIT{_R}" if is_perfect else f"{_RED}{_B}❌ INSUFFISANT{_R}"
            print(f"\n  {verdict}")
            if pt or ct:
                cout_iter = _calculer_cout(pt, ct)
                print(
                    f"  {_DIM}🪙 Tokens iter : {pt} in | {ct} out"
                    f"  —  ${cout_iter:.6f}{_R}"
                )
            if feedback_llm and not is_perfect:
                print(_header("Feedback actionnable du Discriminateur", _RED))
                print(_wrap(feedback_llm))

        # ── Étape 3 : Succès ou recadrage ciblé ──────────────────────────────
        if is_perfect:
            rapport.succes = True
            rapport.iterations_necessaires = i
            if verbose:
                print(
                    _banner(
                        f"✅  SUCCÈS à l'itération {i}  —  Les 3 métriques sont >= 8 !",
                        _GREEN,
                    )
                )
            break

        if i < max_iterations:
            feedback_enrichi = _feedback_contextualise(sf, sr, sc, feedback_llm, i)
            contexte_courant = f"{contexte_initial}\n\n{feedback_enrichi}"
            if verbose:
                print(
                    _header(
                        f"Contexte enrichi avec feedback ciblé → relance itération {i+1}",
                        _CYAN,
                    )
                )
        else:
            if verbose:
                print(
                    _banner(
                        f"⚠️   MAX ITÉRATIONS ATTEINT  "
                        f"—  F={sf} R={sr} C={sc} (seuil : 8)",
                        _RED,
                    )
                )

    # ── Finalisation des métriques FinOps ─────────────────────────────────────
    rapport.latence_totale_s = round(time.perf_counter() - t_start, 2)
    rapport.total_prompt_tokens = total_prompt_tokens
    rapport.total_completion_tokens = total_completion_tokens
    rapport.cout_estime_usd = _calculer_cout(total_prompt_tokens, total_completion_tokens)

    if verbose:
        _afficher_rapport_final(rapport)

    return rapport


# ── Rapport récapitulatif ─────────────────────────────────────────────────────

def _afficher_rapport_final(rapport: AdversarialReport) -> None:

    # ── Section RAGAS ─────────────────────────────────────────────────────────
    print(_banner("RAPPORT FINAL  —  BOUCLE ADVERSARIALE", _CYAN))

    if rapport.succes:
        statut = f"{_GREEN}{_B}SUCCÈS en {rapport.iterations_necessaires} itération(s){_R}"
    else:
        statut = f"{_RED}{_B}ÉCHEC après {len(rapport.iterations)} itération(s){_R}"

    ticket_court = rapport.ticket[:80] + "…" if len(rapport.ticket) > 80 else rapport.ticket
    print(f"\n  Résultat  : {statut}")
    print(f"  Ticket    : {ticket_court}")
    print(f"\n  {_B}Progression des scores par itération :{_R}")

    for it in rapport.iterations:
        def _col(s: int) -> str:
            return (_GREEN if s >= 8 else _YELLOW if s >= 5 else _RED) + str(s) + _R

        line = (
            f"    Iter {it.numero}  "
            f"📊 Fidélité={_col(it.score_faithfulness)}/10  "
            f"🎯 Pertinence={_col(it.score_relevance)}/10  "
            f"📚 Contexte={_col(it.score_context)}/10  "
            f"(moy: {it.score_moyen})"
        )
        print(line, end="")

        if it.is_perfect:
            print(f"  {_GREEN}✅{_R}")
        elif it.feedback.startswith("Erreur proxy"):
            print(f"  {_RED}⚠ Erreur proxy{_R}")
        else:
            print(f"  {_RED}→ recadrage{_R}")

    # ── Section FinOps ────────────────────────────────────────────────────────
    commentaire = _commentaire_rentabilite(rapport.cout_estime_usd)
    total_tokens = rapport.total_prompt_tokens + rapport.total_completion_tokens

    print(_banner("BILAN FINOPS & PERFORMANCES", _GOLD))
    print(f"\n  ⏱  {_B}Latence totale   :{_R} {rapport.latence_totale_s:.2f} secondes")
    print(
        f"  🪙  {_B}Tokens consommés :{_R} "
        f"{rapport.total_prompt_tokens:,} (In)"
        f" | {rapport.total_completion_tokens:,} (Out)"
        f"  —  {total_tokens:,} total"
    )
    print(f"    {_B}Coût estimé      :{_R} {_GREEN}${rapport.cout_estime_usd:.6f} USD{_R}")
    print(f"    {_B}Rentabilité      :{_R} {_GOLD}{commentaire}{_R}")
    print(
        f"\n  {_DIM}Tarification : ${_PRIX_INPUT_PER_M_USD}/M input"
        f" | ${_PRIX_OUTPUT_PER_M_USD}/M output"
        f" (GPT-4o / Claude Sonnet 3.5){_R}"
    )


# ── Démo ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    TICKET_DEMO = (
        "Le VPN Cisco me donne l'erreur 412 et je suis en Chine. "
        "J'ai déjà redémarré mon PC et réinstallé AnyConnect mais rien ne change."
    )

    RCA_GROUND_TRUTH = (
        "L'erreur 412 'Tunnel rejected by server' en Chine est causée par le "
        "blocage du port UDP 1194 (IPSec/IKEv2) par le Great Firewall of China. "
        "La solution est de reconfigurer AnyConnect pour utiliser le port TCP 443 "
        "(TLS fallback) via le profil VPN 'Michelin-China-Fallback'. "
        "Si ce profil est absent du client, l'utilisateur doit contacter le support "
        "N2 pour que l'équipe réseau active le profil de contournement GFW sur son "
        "compte AnyConnect et lui fournisse le fichier de configuration XML."
    )

    run_adversarial_training(
        ticket=TICKET_DEMO,
        rca_ground_truth=RCA_GROUND_TRUTH,
        max_iterations=3,
        modele_agent="phi3:latest",
        # NOTE : Le proxy Copilot (localhost:4141) accepte uniquement les modèles GPT.
        # Remplacez par "claude-sonnet-4-6" si vous utilisez un proxy LiteLLM+Anthropic.
        modele_discriminateur="gpt-5.2",
        contexte_initial="L'entreprise est Michelin. Le VPN principal est Cisco AnyConnect.",
    )
