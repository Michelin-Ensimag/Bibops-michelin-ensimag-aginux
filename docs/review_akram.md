# Plan de lecture — Akram
> Périmètre : Boucle adversariale · Security Arena (équipe Ψ) · Déploiement/Reproduction · Méthodologie

---

## Fichiers à maîtriser (lire en détail)

### Déploiement & Reproduction (30 min)

| Fichier | Ce qu'on y cherche |
|---|---|
| `README.md` | Pitch, prérequis, commandes de démarrage — **tu dois pouvoir guider le jury pas à pas** |
| `pyproject.toml` | Entry-point `bibops`, dépendances clés (ollama, chromadb, langgraph, fastapi…) |
| `requirements.txt` | Liste exacte des dépendances pour la reproduction |
**Questions jury** : Comment reproduire le projet from scratch ? Pourquoi `pip install -e .` ? Pourquoi Ollama + proxy Copilot séparés ?

---

### Méthodologie — Agent ReAct (45 min)

| Fichier | Points clés |
|---|---|
| `src/agent/maestro.py` | [*] **CŒUR** — `lancer_agent()`, boucle ReAct max 5 itérations, `_call_llm()` → `AgentDecision` Pydantic (tool/argument/final_answer), `KEYWORD_ROUTING` (hint, pas contrainte), `MaestroRunTrace` JSONL, fallback déterministe |
| `src/agent/tools.py` | Les 3 outils : `verifier_statut_serveur` (3s), `chercher_dans_kb` (5s, 1 retry), `chercher_documentation_technique` (ChromaDB 8s, 1 retry) — `ToolPolicy` frozen dataclass |

**Questions jury** : Pourquoi max 5 itérations ? Comment le fallback déterministe est-il déclenché ? Pourquoi JSON mode (pas de regex) ?

---

### Boucle adversariale — RAGAS (1h30)

| Ordre | Fichier | Points clés |
|---|---|---|
| 1 | `src/bibops/benchmark/adversarial.py` | [*] Pipeline principal `bibops bench adversarial` — génère des tickets adversariaux, lance ReAct vs Zero-shot, évalue avec discriminateur RAGAS, 10 tickets IT |
| 2 | `src/bibops/benchmark/adversarial_convergence.py` | Boucle de convergence — itère jusqu'à ce que les deux architectures produisent des réponses similaires, métriques de convergence |
| 3 | `src/bibops/evaluation/judges/discriminator.py` | [*] Discriminateur RAGAS-inspired — distingue réponses LLM Unique vs Multi-Agents, calcule le score de différenciation, logique de jugement |

**Questions jury** : Qu'est-ce qu'une boucle adversariale RAGAS ? Comment le discriminateur choisit-il entre les deux architectures ? Qu'est-ce que la convergence mesure ici ? Pourquoi 10 tickets pour `adversarial` ?

---

### Security Arena — Équipe Ψ (1h)

| Ordre | Fichier | Points clés |
|---|---|---|
| 1 | `src/racing/shared/attack_payloads.py` | [*] Templates de payloads adversariaux injectés dans les décisions course — types d'attaques, format des injections |
| 2 | `src/racing/team_psi/main.py` | [*] Équipe Ψ — processus attaquant : lit la télémétrie SSE, construit des décisions malveillantes avec payloads injectés, POST vers Hub |
| 3 | `src/racing/shared/security_metrics.py` | Métriques de détection d'attaques — comment le Hub mesure si une équipe a été compromise |
| 4 | `src/racing/shared/console.py` | Affichage rich console pendant l'arène (pour la démo) |

**Questions jury** : Quel est le vecteur d'attaque de l'équipe Ψ ? Comment les autres équipes se défendent-elles ? Comment `security_race_report.json` est-il généré ?

---

### Security Arena — Détecteurs (45 min)

| Fichier | Points clés |
|---|---|
| `src/bibops/evaluation/checks.py` | Détecteurs purs : PII regex, secrets (Bearer/api_key), injection markers, refusal phrases, `extract_urls()`, toxicity heuristic |
| `src/bibops/evaluation/security_profile.py` | `SecurityProfile` dataclass — markers, seuils, `enabled_checks`, `block_threshold` |
| `src/bibops/evaluation/security_evaluator.py` | `SecurityLLMInspectorAdapter` — `_RiskPack` (6 dimensions), scoring 0–10, `findings` format `dimension:detail` |

**Questions jury** : Comment `_RiskPack` agrège-t-il les 6 dimensions en score 0–10 ? Quelle est la différence entre `checks.py` (règles pures) et `security_evaluator.py` (scoring) ?

---

## Fichiers à parcourir rapidement (skim)

| Fichier | Pourquoi le parcourir |
|---|---|
| `src/agent/rag.py` | Comprendre l'outil RAG ChromaDB que le ReAct utilise (contexte pour adversarial) |
| `src/agent/memory.py` | `MemoCourTerme` — mémoire court terme injectée dans le contexte LLM |
| `src/racing/start_arena.py` | Comment les 4 processus (Hub + 3 équipes + Ψ) sont lancés en parallèle |
| `src/racing/hub/server.py` | FastAPI Hub — routes SSE, POST decision — contexte de l'arène |
| `src/racing/hub/race_engine.py` | 50 laps, 3s/lap — générateur de télémétrie |
| `src/racing/team_validated/main.py` | Équipe C (validée) — comment elle se défend contre les attaques |
| `src/racing/state.py` | `RacingState`, `TelemetryData`, `FinalDecision` — contrats de données arène |
| `src/bibops/cli/commands/bench.py` | Commandes `bibops bench adversarial`, `adversarial-demo` |
| `src/bibops/cli/commands/racing.py` | Commandes `bibops racing adversarial`, `arena` |
| `src/common/config.py` | Constantes globales — modèles par défaut, timeouts |

---

## Résultats à connaître

| Fichier de données | Ce qu'il contient |
|---|---|
| `data/outputs/benchmark/adversarial_convergence.json` | Résultats de la boucle de convergence adversariale |
| `data/outputs/benchmark/security_race_report.json` | Rapport de sécurité arène : attaques détectées, équipes compromises |

---

## Résumé — fichiers critiques

```
README.md + pyproject.toml + requirements.txt   ← reproduction
src/agent/maestro.py                             ← méthodologie ReAct
src/agent/tools.py                               ← outils agent
src/bibops/benchmark/adversarial.py              ← boucle adversariale
src/bibops/benchmark/adversarial_convergence.py  ← convergence
src/bibops/evaluation/judges/discriminator.py    ← discriminateur RAGAS
src/racing/team_psi/main.py                      ← vecteur d'attaque
src/racing/shared/attack_payloads.py             ← payloads adversariaux
src/racing/shared/security_metrics.py            ← métriques sécurité
src/bibops/evaluation/checks.py                  ← détecteurs règles
src/bibops/evaluation/security_evaluator.py      ← scoring sécurité
```

---

## Questions probables du jury

- Comment reproduire le projet sur une nouvelle machine ? Quelles sont les dépendances critiques ?
- Comment fonctionne la boucle ReAct de `lancer_agent()` ? (max iterations, fallback, JSON mode)
- Qu'est-ce qu'une boucle adversariale RAGAS-inspired et en quoi diffère-t-elle d'un benchmark classique ?
- Comment le discriminateur distingue-t-il les réponses LLM Unique vs Multi-Agents ?
- Qu'est-ce que la convergence adversariale mesure et pourquoi est-ce pertinent ?
- Quel est le vecteur d'attaque de l'équipe Ψ et comment fonctionne l'injection dans les décisions course ?
- Comment `SecurityLLMInspectorAdapter` calcule-t-il son score 0–10 depuis `_RiskPack` ?
- Quelle est la différence entre `bibops bench adversarial` et `bibops racing adversarial` ?
- Comment les payloads de `attack_payloads.py` sont-ils construits pour tromper les agents ?
