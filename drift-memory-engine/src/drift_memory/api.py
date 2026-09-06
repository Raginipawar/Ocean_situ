"""
FastAPI Server for Drift Memory Engine (Person 2 / Intelligence Core #2).

Exposes:
  - GET  /health: Service status & sub-basin configuration
  - GET  /alerts: Active drift & surprise alerts (consumed by Person 5 / CesiumJS)
  - GET  /memory/state: Test-time memory inspection across all BoB sub-basins
  - POST /scenario: Switch demonstration scenario (nominal, marine_heatwave, etc.)
  - POST /evaluate/fused: Direct evaluation of Person 1's /fused payload
  - POST /evaluate/raw: Evaluation of paired Model & Observation snapshots
  - POST /reset: Clear memory cells & debounce caches
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .config import SUB_BASINS, settings
from .scenarios import AnomalyScenario
from .schemas import (
    Alert,
    FusedResponse,
    MemorySnapshotResponse,
    ModelSnapshot,
    ObservationSnapshot,
)
from .service import DriftMemoryService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("drift_memory.api")

app = FastAPI(
    title="VARUNA - Drift Memory Engine",
    description=(
        "SIH26067 VARUNA, Person 2 / Intelligence Core #2. "
        "Calculates rolling model-vs-reality divergence and test-time 'surprise' "
        "memory scores, triggering live early-warning alerts for marine heatwaves, "
        "current shear, and forecast drift."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

service = DriftMemoryService()


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "drift_memory_engine",
        "track": "Person 2 (Intelligence Core #2)",
        "region": settings.region_name,
        "sub_basins": [basin.name for basin in SUB_BASINS],
        "active_scenario": service.current_scenario.value,
    }


@app.get("/alerts", response_model=list[Alert])
async def get_alerts(
    scenario: Optional[AnomalyScenario] = Query(
        None, description="Override scenario (nominal, marine_heatwave, boundary_current_shear, compound_anomaly)"
    ),
    use_upstream: bool = Query(
        False, description="Attempt live fetch from Person 1's /fused endpoint first"
    ),
) -> list[Alert]:
    """
    Return active divergence alerts.
    
    This is Person 2's primary deliverable, consumed by Person 5's REST/WebSocket
    and rendered in the CesiumJS alert panel.
    """
    try:
        if use_upstream:
            return await service.fetch_upstream_fused_and_evaluate()
        return service.get_alerts(scenario=scenario)
    except Exception as exc:
        logger.exception("Failed to compute drift alerts")
        raise HTTPException(status_code=500, detail=f"Drift evaluation failed: {exc}") from exc


@app.get("/memory/state", response_model=MemorySnapshotResponse)
def get_memory_state() -> MemorySnapshotResponse:
    """Return rolling test-time memory state across all sub-basins."""
    return service.get_memory_snapshot()


@app.post("/scenario/{scenario_name}")
def set_scenario(scenario_name: AnomalyScenario) -> dict:
    """Switch active demo scenario."""
    service.set_scenario(scenario_name)
    return {
        "status": "scenario_updated",
        "scenario": scenario_name.value,
    }


@app.post("/evaluate/fused", response_model=list[Alert])
def evaluate_fused(fused: FusedResponse) -> list[Alert]:
    """Directly evaluate drift on Person 1's /fused payload."""
    try:
        return service.evaluate_fused(fused)
    except Exception as exc:
        logger.exception("Fused evaluation failed")
        raise HTTPException(status_code=500, detail=f"Failed to evaluate fused response: {exc}") from exc


@app.post("/evaluate/raw", response_model=list[Alert])
def evaluate_raw(payload: dict) -> list[Alert]:
    """Evaluate drift on paired model and observation snapshots."""
    try:
        model = ModelSnapshot.model_validate(payload.get("model", {}))
        obs = ObservationSnapshot.model_validate(payload.get("observations", {}))
        return service.evaluate_raw(model, obs)
    except Exception as exc:
        logger.exception("Raw evaluation failed")
        raise HTTPException(status_code=400, detail=f"Invalid payload format: {exc}") from exc


@app.post("/reset")
def reset_memory() -> dict:
    """Clear memory cells and debounce cache."""
    service.reset()
    return {"status": "memory_reset", "message": "All sub-basin memory cells cleared"}
