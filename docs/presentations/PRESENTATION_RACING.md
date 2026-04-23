# BibOps Racing Arena — Script du Présentateur

> **Document confidentiel — Soutenance PFE Michelin/Ensimag**
> Garde ce fichier ouvert sur un écran secondaire pendant la démo.

---

## 1. ELEVATOR PITCH — 2 minutes chrono

### Ce qu'il faut dire (version non-technique, pour ouvrir la présentation)

> *"Imaginez trois ingénieurs dans un mur des stands de Formule 1 : un spécialiste pneus, un spécialiste carburant, un ingénieur de course. À chaque tour, ils reçoivent la télémétrie de la voiture et doivent se concerter pour répondre à une seule question : est-ce qu'on entre aux stands maintenant, ou on reste en piste ?*
>
> *Nous avons remplacé ces trois ingénieurs par des LLMs. Mais pas un seul LLM — plusieurs équipes rivales, chacune pilotée par un modèle différent, toutes en compétition sur la même course, en temps réel.*
>
> *C'est la BibOps Racing Arena : un banc d'évaluation dynamique pour LLMs, déguisé en course automobile."*

---

### Pourquoi c'est le "Benchmark MLOps ultime" — l'argument clé

La distinction fondamentale à marteler devant le jury :

| Benchmark **statique** (méthode classique) | Benchmark **dynamique** (notre approche) |
|---|---|
| Même question → score fixe | La course évolue → la bonne réponse change à chaque tour |
| Évalue la connaissance | Évalue le **raisonnement sous contrainte** |
| Reproductible à l'identique | Stochastique : météo, safety car, usure pneus |
| Un LLM isolé | Plusieurs LLMs en **compétition simultanée** sur le même état |
| Résultat : un nombre | Résultat : une **stratégie observable** tour par tour |

> **Phrase à retenir** : *"Nous n'évaluons pas ce que le modèle sait. Nous évaluons comment il décide sous pression, face à de l'incertitude, avec des contraintes qui changent."*

---

### La justification technique en une phrase

> *"Chaque équipe est un système multi-agents distribué — un graphe LangGraph async — qui consulte dynamiquement la documentation technique Michelin via RAG pour prendre ses décisions. Le Hub central synchronise tout via Server-Sent Events. Chaque processus est isolé. Tout tourne en local."*

---

## 2. CHORÉGRAPHIE DE LA DÉMO EN DIRECT

### Pré-requis : préparer son environnement AVANT d'entrer dans la salle

```bash
# Vérifier que le proxy Copilot répond
curl -s http://localhost:4141/v1/models | python -m json.tool

# Vérifier qu'Ollama tourne (pour le RAG)
ollama list

# Nettoyer les anciens logs
rm -f logs/arena/*.log
```

Ouvrir **4 panneaux de terminal** (iTerm2 split ou tmux) :
- **Haut gauche** : proxy Copilot
- **Haut droit** : Arena launcher (`start_arena.py`)
- **Bas gauche** : logs d'une écurie en direct
- **Bas droit** : monitoring Hub (`watch` + `curl`)

---

### Étape 0 — Ingestion RAG (si pas encore faite, ~2 min)

> *"Avant la course, nos agents ont accès à la documentation officielle Michelin Motorsport. On vectorise ces documents une seule fois dans ChromaDB."*

```bash
python -m src.bibops.racing.hub.ingest_racing
```

**Ce qu'on montre** : les 3 fichiers dans `data/knowledge_base/racing_docs/` (compounds, physics, strategy). Insister : *"C'est la vraie documentation technique — pas du prompt engineering à la main."*

---

### Étape 1 — Lancer le proxy Copilot (Terminal 1)

```bash
npx copilot-api@latest start
```

Attendre le message de démarrage. Expliquer en une phrase :

> *"Ce proxy expose une interface OpenAI-compatible en local. Nos agents croient parler à l'API OpenAI — en réalité ils passent par GitHub Copilot. Zéro coût, zéro donnée envoyée en dehors."*

---

### Étape 2 — Lancer l'Arena (Terminal 2)

```bash
python -m src.bibops.racing.start_arena
```

**Pendant les 4 secondes d'attente du Hub**, expliquer l'architecture :

> *"Le Hub démarre en premier — c'est un serveur FastAPI qui détient la simulation de course. Les écuries se connectent ensuite. La course ne démarre que quand tous les clients sont connectés — c'est le INITIAL_WAIT_SECONDS dans race_engine.py."*

**Pointer** le tableau affiché dans le terminal :
```
✓ Ferrari_Pro      modèle=gpt-4o      PID=XXXX
✓ RedBull_Fast     modèle=gpt-4o-mini  PID=XXXX
✓ McLaren_New      modèle=gpt-4.1     PID=XXXX
```

> *"Trois processus complètement indépendants. Chacun a son propre graphe LangGraph, sa propre mémoire de tour, son propre LLM. Ils ne se parlent pas directement — ils passent tous par le Hub."*

---

### Étape 3 — Suivre une écurie en direct (Terminal 3)

```bash
tail -f logs/arena/team_Ferrari_Pro.log
```

**WOW MOMENT N°1 — Le RAG en action** *(à montrer au tour ~3-5)*

Dans les logs, chercher une ligne comme :
```
[Ferrari_Pro]   ⟳ réflexion en cours...
```

Ouvrir simultanément le log du Hub :
```bash
tail -f logs/arena/hub.log
```

Vous verrez apparaître :
```
[RAG] Écurie 'Ferrari_Pro' → "Quelles sont les spécifications du composé MEDIUM..."
```

> **Ce qu'on dit** : *"Regardez — l'agent pneus de Ferrari_Pro vient de faire un appel HTTP asynchrone vers le Hub pour interroger la documentation Michelin. Il ne se contente pas de raisonner sur la télémétrie : il consulte les specs techniques. C'est un agent à l'intérieur d'un agent — un mini ReAct loop dans le nœud tire_expert, avec tool calling natif LangChain."*

---

### Étape 4 — Monitoring Hub (Terminal 4)

```bash
watch -n 3 "curl -s http://localhost:8000/status | python -m json.tool"
```

**WOW MOMENT N°2 — Le changement météo** *(tour 15 → pluie légère, tour 30 → pluie forte)*

Quand la météo bascule, pointer en live dans les logs la divergence de décisions entre les équipes :

```bash
curl -s http://localhost:8000/results | python -m json.tool | grep -A5 '"action"'
```

> **Ce qu'on dit** : *"Tour 30 — pluie forte. Le même état de course, trois LLMs différents, trois décisions potentiellement différentes. Ferrari avec gpt-4o a-t-il pris la même décision que RedBull avec gpt-4o-mini ? C'est exactement ça qu'on benchmark : la qualité du raisonnement stratégique sous changement de conditions."*

---

### Étape 5 — Le tableau de bord benchmark final

À la fin de la course (50 tours × 3s ≈ **2 min 30**) :

```bash
curl -s http://localhost:8000/results | python -m json.tool
```

**WOW MOMENT N°3 — Le comparatif multi-LLMs**

La réponse JSON affiche pour chaque écurie :
```json
"Ferrari_Pro":  { "model": "gpt-4o",      "box_count": 2, "stay_count": 48 },
"RedBull_Fast": { "model": "gpt-4o-mini",  "box_count": 4, "stay_count": 46 },
"McLaren_New":  { "model": "gpt-4.1",      "box_count": 3, "stay_count": 47 }
```

> **Ce qu'on dit** : *"En 2 minutes 30, on a collecté la trace complète de toutes les décisions de trois LLMs différents, sur la même course. `box_count` vs `stay_count` — est-ce que le modèle sur-réagit à la pluie ? Est-ce qu'il change de pneus trop tôt ou trop tard ? On peut recréer la course entière, comparer les raisonnements ligne par ligne. C'est un dataset d'évaluation qu'on génère en temps réel."*

---

### Timeline complète de la démo

| Temps | Action | Ce qu'on dit |
|---|---|---|
| T+0:00 | `start_arena.py` | Architecture distribuée, 3 processus isolés |
| T+0:10 | Hub démarré | FastAPI + SSE broadcast |
| T+0:15 | Écuries connectées, course démarre | LangGraph compilé, état partagé |
| T+0:45 | **WOW #1** — RAG visible dans hub.log | Tool calling async, RAG server-side |
| T+1:20 | **WOW #2** — Météo bascule (T15/T30) | Benchmark dynamique, divergence des LLMs |
| T+2:30 | Fin de course, `curl /results` | **WOW #3** — Comparatif benchmark final |

---

## 3. ARGUMENTS TECHNIQUES — Questions/Réponses

### Concepts d'ingénierie avancés à mentionner

#### A. Architecture distribuée event-driven (SSE Broadcast)

**Concept** : Un seul `asyncio.Task` (`_race_loop`) tourne en arrière-plan dans le Hub. Chaque client SSE reçoit sa propre `asyncio.Queue`. Le broadcast (`_broadcast`) publie dans toutes les queues simultanément.

**Argument jury** : *"Ce n'est pas du polling. Les écuries ne demandent pas la télémétrie — elle leur est poussée. C'est le patron Publisher/Subscriber, implémenté nativement en Python async sans message broker externe."*

**Référence code** : `hub/race_engine.py:113` — `subscribe()` → `asyncio.Queue`.

---

#### B. LangGraph State Machine avec routage conditionnel

**Concept** : Le graphe LangGraph n'est pas une chaîne linéaire. C'est un **automate à états finis** où le superviseur lit `state["messages"]`, détecte les experts déjà consultés, et route dynamiquement vers le prochain nœud.

**Argument jury** : *"La topologie du graphe est déclarative — on définit les arêtes une seule fois à la compilation. Le routage conditionnel est une fonction pure qui lit l'état. C'est séparation totale entre la logique de flux et la logique métier."*

**Référence code** : `team_client/graph.py:35` — `_route_from_principal()` + `add_conditional_edges`.

---

#### C. Structured Output / Function Calling contraint

**Concept** : `llm.with_structured_output(RoutingDecision)` et `llm.with_structured_output(FinalDecision)` forcent le LLM à retourner un objet Pydantic valide. `FinalDecision.action` est un `Literal["STAY OUT", "BOX BOX"]` — le modèle ne peut pas halluciner une troisième option.

**Argument jury** : *"On ne parse pas du texte libre. On contraint la sortie LLM au niveau du schéma. Si le modèle essaie de sortir du cadre, Pydantic lève une ValidationError avant que ça atteigne le code métier. C'est de la robustesse par construction."*

**Référence code** : `team_client/nodes.py:53-66` — `FinalDecision` Pydantic model.

---

#### D. RAG Server-Side distribué (outil LangChain async)

**Concept** : `ask_michelin_engineer` est un `@tool` LangChain décoré, async. Il fait un `httpx.AsyncClient.post` vers `Hub/ask_michelin`, qui interroge ChromaDB via `OllamaEmbeddings`. Le modèle d'embedding tourne sur Ollama — 100% local.

**Argument jury** : *"Le RAG n'est pas embarqué dans l'agent. Il est hébergé côté Hub et exposé comme un service HTTP. N'importe quelle écurie peut l'interroger. C'est une séparation retrieval/reasoning — le LLM ne touche jamais ChromaDB directement."*

**Référence code** : `team_client/state_tools.py:47` — `ask_michelin_engineer` tool + `hub/rag_service.py:40` — lazy singleton.

---

#### E. Isolation par processus (vs threads)

**Concept** : `start_arena.py` lance chaque écurie via `subprocess.Popen`. Chaque processus a son propre espace mémoire. La variable globale `MODEL` dans `nodes.py` est modifiée **avant** l'import du graphe compilé, ce qui permet d'injecter un modèle différent par processus sans aucune concurrence.

**Argument jury** : *"On aurait pu utiliser des threads. On a choisi des processus pour une raison précise : garantir l'isolation totale des états entre les écuries. Un crash de Ferrari_Pro n'affecte pas RedBull_Fast. C'est le principe de fault isolation."*

**Référence code** : `team_client/main.py:44-48` — injection du modèle avant import du graphe.

---

#### F. Agent imbriqué — Mini ReAct dans un nœud LangGraph

**Concept** : `tire_expert_node` contient sa propre boucle ReAct (max 3 itérations) : `LLM → tool_call? → execute → LLM → ...`. Un nœud du graphe LangGraph est lui-même un mini-agent avec tool calling.

**Argument jury** : *"C'est de la composabilité d'agents. LangGraph gère la macro-orchestration (quel expert consulter). Chaque expert gère sa micro-orchestration (est-ce que j'ai besoin de consulter la doc Michelin avant de répondre). Deux niveaux d'agentivité, deux boucles séparées."*

**Référence code** : `team_client/nodes.py:127-145` — boucle `for _ in range(3)` dans `tire_expert_node`.

---

### Questions pièges probables et réponses préparées

**Q : "Pourquoi ne pas avoir utilisé CrewAI ou AutoGen plutôt que LangGraph ?"**

> *"LangGraph nous donne un contrôle explicite sur le graphe d'exécution — on voit exactement quel nœud s'active et pourquoi. CrewAI et AutoGen sont des frameworks de plus haut niveau qui cachent ce routing. Pour un contexte de benchmark et d'évaluation, on a besoin d'observabilité totale sur chaque étape. LangGraph rend le flux introspectable."*

**Q : "La course est simulée — ce n'est pas du vrai temps réel."**

> *"La simulation est un choix délibéré. Elle nous permet de rejouer exactement le même scénario météo pour comparer les LLMs sur des conditions identiques. En compétition réelle, les conditions changent entre deux runs — on ne peut pas comparer. Notre simulation est un environnement contrôlé reproductible, ce qui est une exigence fondamentale du benchmark."*

**Q : "Comment vous mesurez lequel des LLMs est 'meilleur' ?"**

> *"Aujourd'hui on mesure comportementalement : fréquence de pit stop, timing par rapport aux changements météo, cohérence pneus/conditions. L'extension naturelle — qu'on a architecturée mais pas encore implémentée — c'est un moteur de scoring post-course : comparer la décision de chaque écurie avec la décision 'optimale' calculée a posteriori sur les données de télémétrie complètes."*

**Q : "Pourquoi GitHub Copilot comme proxy et pas l'API OpenAI directement ?"**

> *"Contrainte Michelin : pas d'API key externe dans le projet. Le proxy Copilot nous permet d'utiliser des modèles GPT en local, sans exposer de credentials et sans coût par token. C'est le même pattern qu'un proxy interne d'entreprise — exactement ce que Michelin déploierait en production."*

---

## 4. ARCHITECTURE EN UN SCHÉMA (à afficher sur slide)

```
┌─────────────────────────────────────────────────────────────────┐
│                     BibOps Racing Arena                         │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    HUB  :8000  (FastAPI)                  │   │
│  │                                                          │   │
│  │  ┌──────────────┐  SSE broadcast  ┌──────────────────┐  │   │
│  │  │  RaceEngine  │ ──────────────► │  /stream          │  │   │
│  │  │  50 tours    │                 └──────────────────┘  │   │
│  │  │  3s/tour     │                                       │   │
│  │  └──────────────┘  ┌──────────────────────────────────┐ │   │
│  │                    │  RacingRAG  (ChromaDB + Ollama)   │ │   │
│  │                    │  collection : "racing_kb"         │ │   │
│  │                    │  /ask_michelin  ◄──── HTTP POST   │ │   │
│  │                    └──────────────────────────────────┘ │   │
│  │                    ┌──────────────────────────────────┐ │   │
│  │                    │  /decision/{team_id}  ◄─ POST    │ │   │
│  │                    │  /results  ► benchmark JSON      │ │   │
│  │                    └──────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Processus Ferrari_Pro          Processus RedBull_Fast           │
│  ┌─────────────────────────┐   ┌─────────────────────────┐      │
│  │ LangGraph (TeamState)   │   │ LangGraph (TeamState)   │      │
│  │                         │   │                         │      │
│  │  team_principal (gpt-4o)│   │  team_principal (mini)  │      │
│  │    ├─► tire_expert      │   │    ├─► tire_expert      │      │
│  │    │     └─► RAG tool ──┼───┼──► Hub /ask_michelin    │      │
│  │    └─► fuel_expert      │   │    └─► fuel_expert      │      │
│  └─────────────────────────┘   └─────────────────────────┘      │
│           │  SSE listen                  │  SSE listen           │
│           │  POST /decision              │  POST /decision       │
│           └──────────────────────────────┘                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. OUVERTURE — Ce qu'on ouvre comme perspective pour Michelin

Terminer la soutenance sur cette vision :

> *"Ce qu'on a construit ici est transposable directement au cœur de métier Michelin. Remplacez 'pneus de course' par 'pneumatiques industriels', remplacez 'télémétrie F1' par les données IoT de vos capteurs de pression en flotte, et remplacez les trois ingénieurs par vos experts métier modélisés en agents. L'architecture est la même : un Hub central, des agents distribués, un RAG sur vos documents techniques, et un benchmark dynamique pour choisir quel LLM prend les meilleures décisions sur vos données réelles. BibOps Racing Arena est un proof-of-concept d'architecture MLOps multi-agents souveraine — local-first, zéro cloud, entièrement auditables."*

---

*Script généré à partir de l'analyse exhaustive du code source de `src/bibops/racing/`.*
*Michelin/Ensimag — Soutenance PFE 2025-2026*
