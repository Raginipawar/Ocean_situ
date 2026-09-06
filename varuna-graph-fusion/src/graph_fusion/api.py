"""
FastAPI surface for the Graph Fusion Engine track.

Exposes /model and /observations (mock-backed today, adapter-swappable to
Person 4 / Person 6's real endpoints on Day 3 -- see adapters.py) purely so
this track is independently runnable and testable via curl/Postman from Day 1,
matching the "everyone builds against an agreed API contract, so nobody
blocks anybody" rule in the Round-2 work distribution doc.

/fused is this track's actual deliverable: it runs the Graph Fusion Engine
(GNN, auto-falling-back to the graph-weighted engine) over whatever /model
and /observations currently return.

Run:
    uvicorn graph_fusion.api:app --reload --port 8000
"""
from __future__ import annotations

import logging
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .adapters import get_model_source, get_observation_source
from .fusion_service import FusionService
from .schemas import FusedResponse, ModelSnapshot, ObservationSnapshot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("graph_fusion.api")

app = FastAPI(
    title="VARUNA - Graph Fusion Engine",
    description=(
        "SIH26067 VARUNA, Person 1 / Intelligence Core #1. "
        "Serves /model and /observations as mock adapters until Person 4's and "
        "Person 6's real pipelines are wired in (see adapters.py), and /fused as "
        "the graph-based correction of the model grid against real sensor readings."
    ),
    version="0.1.0",
)

# Dev-friendly CORS: the frontend (Vite, localhost:5173) runs on a different
# origin than this API (localhost:8000). Tighten this to the real deployed
# frontend origin(s) before this ever goes anywhere but a laptop.
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ALLOWED_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
)

_fusion_service = FusionService()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "region": config.REGION_NAME}


@app.get("/model", response_model=ModelSnapshot)
def get_model() -> ModelSnapshot:
    try:
        return get_model_source().fetch()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Model source unavailable: {exc}") from exc


@app.get("/observations", response_model=ObservationSnapshot)
def get_observations() -> ObservationSnapshot:
    try:
        return get_observation_source().fetch()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Observation source unavailable: {exc}") from exc


@app.get("/fused", response_model=FusedResponse)
def get_fused(
    engine: Literal["auto", "gnn", "fallback"] = Query(
        "auto", description="Force a specific engine, or let it auto-fallback."
    )
) -> FusedResponse:
    try:
        model = get_model_source().fetch()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Model source unavailable: {exc}") from exc

    try:
        obs = get_observation_source().fetch()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Observation source unavailable: {exc}") from exc

    try:
        return _fusion_service.fuse(model, obs, engine=engine)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Fusion failed")
        raise HTTPException(status_code=500, detail=f"Fusion failed: {exc}") from exc
