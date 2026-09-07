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

from . import config, volumetric
from .adapters import get_depth_profile_source, get_model_source, get_nowcast_info_source, get_observation_source
from .fusion_service import FusionService
from .schemas import (
    DepthProfileSnapshot,
    FusedResponse,
    ModelSnapshot,
    NowcastInfo,
    ObservationSnapshot,
    VolumetricCellSeries,
    VolumetricMeta,
    VolumetricSnapshot,
)

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


@app.get("/profiles", response_model=DepthProfileSnapshot)
def get_profiles() -> DepthProfileSnapshot:
    """Real depth-resolved observations (Argo/glider/CTD casts get genuine
    multiple levels; surface-only instruments get a real single level) --
    powers the 3D Cube Explorer. See adapters.InsituDepthProfileSource."""
    try:
        return get_depth_profile_source().fetch()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Depth profile source unavailable: {exc}") from exc


@app.get("/nowcast/info", response_model=NowcastInfo)
def get_nowcast_info() -> NowcastInfo:
    """Person 3's Nowcast Engine real training/evaluation results, read live
    from its committed artifacts. See adapters.NowcastInfoSource for why
    this isn't live per-click inference."""
    return get_nowcast_info_source().fetch()


@app.get("/volumetric/meta", response_model=VolumetricMeta)
def get_volumetric_meta() -> VolumetricMeta:
    """Real grid axes (lat/lon/depth/time) for the 3D Cube Explorer's
    free-roam navigation. See volumetric.py."""
    try:
        return VolumetricMeta.model_validate(volumetric.get_meta())
    except volumetric.VolumetricUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/volumetric/snapshot", response_model=VolumetricSnapshot)
def get_volumetric_snapshot(
    day_index: int = Query(-1, description="Index into the real time axis; -1 = most recent real day"),
) -> VolumetricSnapshot:
    """The full real grid (every depth/lat/lon cell), one real day, every
    variable -- what the whole-Bay-of-Bengal free-roam view is colored by."""
    try:
        return VolumetricSnapshot.model_validate(volumetric.get_snapshot(day_index))
    except volumetric.VolumetricUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (IndexError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid day_index: {exc}") from exc


@app.get("/volumetric/cell", response_model=VolumetricCellSeries)
def get_volumetric_cell(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
) -> VolumetricCellSeries:
    """The full real 270-day time series for the grid cell nearest (lat,
    lon), across all real depth levels -- fetched only for the currently
    open cube, backed by the full 724MB dataset."""
    try:
        return VolumetricCellSeries.model_validate(volumetric.get_cell_series(lat, lon))
    except volumetric.VolumetricUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
