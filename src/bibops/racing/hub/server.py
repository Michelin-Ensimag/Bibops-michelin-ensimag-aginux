"""
Racing Hub — FastAPI Server
Point d'entrée HTTP de la Distributed AI Arena.

Routes :
  GET  /stream              → flux SSE broadcast (toutes les écuries voient la même course)
  POST /decision/{team_id}  → reçoit la décision d'une écurie, met à jour la simulation
  POST /ask_michelin        → RAG documentaire Michelin Motorsport
  GET  /status              → snapshot JSON de la course
  GET  /results             → historique complet de toutes les décisions (benchmark)

Lancement :
  python -m src.bibops.racing.hub.server
"""

from __future__ import annotations

from datetime import datetime

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.bibops.racing.hub.race_engine import RaceEngine
from src.bibops.racing.hub.rag_service import RacingRAG


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="BibOps Racing Hub",
    description="Distributed AI Arena — serveur maître de télémétrie F1/WEC",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

engine     = RaceEngine()
racing_rag = RacingRAG()

# Historique des décisions de toutes les écuries (benchmark)
race_history: list[dict] = []


# ---------------------------------------------------------------------------
# Schémas
# ---------------------------------------------------------------------------

class TeamDecision(BaseModel):
    """Décision stratégique envoyée par une écurie participante."""
    action:     str               # "BOX BOX" ou "STAY OUT"
    tires:      str | None = None # compound cible : "WET", "INTERMEDIATE", "SOFT"…
    fuel_added: str | None = None # "full" | "partial" | "none"
    model:      str | None = None # modèle LLM qui a pris la décision
    message:    str | None = None # justification libre


class AskMichelinRequest(BaseModel):
    team_id: str
    query:   str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/stream", summary="Flux SSE broadcast (toutes les écuries)")
async def stream_telemetry() -> StreamingResponse:
    """
    Ouvre un flux Server-Sent Events partagé.
    Toutes les écuries connectées reçoivent la même télémétrie simultanément.
    La course démarre automatiquement 5 s après la première connexion.
    """
    return StreamingResponse(
        engine.subscribe(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/decision/{team_id}", summary="Soumettre une décision stratégique")
async def receive_decision(team_id: str, decision: TeamDecision) -> dict:
    """Reçoit la décision d'une écurie et applique l'effet sur la simulation."""
    lap     = engine.state.lap_current
    weather = engine.state.weather

    if lap == 0:
        raise HTTPException(
            status_code=409,
            detail="La course n'a pas encore démarré.",
        )

    # ── Stocker dans l'historique ──────────────────────────────────────
    race_history.append({
        "timestamp":  datetime.now().isoformat(timespec="seconds"),
        "lap":        lap,
        "team_id":    team_id,
        "model":      decision.model or "?",
        "action":     decision.action,
        "tires":      decision.tires,
        "fuel_added": decision.fuel_added,
        "reasoning":  decision.message,
    })

    # ── Log coloré dans la console du Hub ─────────────────────────────
    model_tag = f" (propulsée par {decision.model})" if decision.model else ""
    if decision.action.upper() == "BOX BOX":
        print(
            f"\n🏆 [DECISION] L'écurie {team_id}{model_tag} a décidé de BOX BOX ! "
            f"→ Pneus : {decision.tires or '?'} | Tour : {lap}"
        )
        engine.apply_pit_stop(decision.tires, decision.fuel_added)
    else:
        print(
            f"\n🟢 [DECISION] L'écurie {team_id}{model_tag} reste en piste "
            f"(STAY OUT) | Tour : {lap}"
        )

    return {
        "status":       "received",
        "team_id":      team_id,
        "lap":          lap,
        "action":       decision.action,
        "tires":        decision.tires,
        "fuel_added":   decision.fuel_added,
        "history_size": len(race_history),
    }


@app.post("/ask_michelin", summary="Interroger la documentation Michelin Motorsport")
async def ask_michelin(request: AskMichelinRequest) -> dict:
    """Recherche vectorielle dans la base documentaire racing_kb."""
    print(
        f"\n[RAG] Écurie '{request.team_id}' → "
        f"\"{request.query[:80]}{'...' if len(request.query) > 80 else ''}\""
    )
    context = await racing_rag.ask_question(request.query)
    return {"team_id": request.team_id, "query": request.query, "context": context}


@app.get("/status", summary="Snapshot de l'état courant")
async def get_status() -> dict:
    return engine.state.to_dict()


@app.get("/results", summary="Historique des décisions — tableau de bord benchmark")
async def get_results() -> dict:
    """
    Retourne toutes les décisions prises par toutes les écuries depuis le début.
    Utile pour comparer les stratégies des différents LLMs.
    """
    # Résumé par écurie
    summary: dict[str, dict] = {}
    for entry in race_history:
        tid = entry["team_id"]
        if tid not in summary:
            summary[tid] = {
                "model":       entry["model"],
                "box_count":   0,
                "stay_count":  0,
                "decisions":   [],
            }
        if entry["action"].upper() == "BOX BOX":
            summary[tid]["box_count"] += 1
        else:
            summary[tid]["stay_count"] += 1
        summary[tid]["decisions"].append({
            "lap":    entry["lap"],
            "action": entry["action"],
            "tires":  entry["tires"],
        })

    return {
        "race_lap":    engine.state.lap_current,
        "total_decisions": len(race_history),
        "teams":       summary,
        "full_log":    race_history,
    }


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        "src.bibops.racing.hub.server:app",
        host="localhost",
        port=8000,
        reload=False,
        log_level="info",
    )
