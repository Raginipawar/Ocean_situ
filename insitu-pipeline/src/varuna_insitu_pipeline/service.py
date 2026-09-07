"""
VARUNA In-Situ Pipeline — Standalone FastAPI Microservice.

Exposes:
- GET /observations : Canonical in-situ observation snapshot for Person 1 (/fused) and Person 5 (backend)
- GET /profiles     : 3D depth-resolved vertical profiles for inspection
- GET /adapters     : List of registered and active sensor adapters
- GET /qc-report    : Detailed quality control metrics from latest run
- GET /health       : Microservice health check
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Query, status
from fastapi.middleware.cors import CORSMiddleware

from .adapters.registry import AdapterRegistry
from .config import settings
from .pipeline import InSituPipeline
from .schemas import (
    ObservationSnapshot,
    QualityControlReport,
    RegionBounds,
    VerticalProfile,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("varuna.insitu.api")

app = FastAPI(
    title="VARUNA In-Situ Data Pipeline API",
    description="In-situ marine observations ingestion, adapter pattern, and quality control service (SIH26067).",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pipeline = InSituPipeline()

# In-memory cache for latest run
_latest_snapshot: ObservationSnapshot | None = None
_latest_profiles: list[VerticalProfile] | None = None
_latest_qc_report: QualityControlReport | None = None


@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """Health check returning active status and available adapters."""
    return {
        "status": "healthy",
        "service": "varuna-insitu-pipeline",
        "active_source": settings.active_source,
        "region": settings.region_name,
        "registered_adapters": AdapterRegistry.list_adapters(),
    }


@app.get("/adapters")
async def list_adapters():
    """Return all discovered and registered sensor adapters."""
    return {
        "active_source": settings.active_source,
        "registered_adapters": AdapterRegistry.list_adapters(),
        "enabled_in_composite": settings.enabled_adapters,
    }


@app.get("/observations", response_model=ObservationSnapshot)
async def get_observations(
    source: str | None = Query(None, description="Override source adapter ('local_demo', 'argovis', 'composite')"),
    lat_min: float | None = Query(None, description="Minimum latitude"),
    lat_max: float | None = Query(None, description="Maximum latitude"),
    lon_min: float | None = Query(None, description="Minimum longitude"),
    lon_max: float | None = Query(None, description="Maximum longitude"),
) -> ObservationSnapshot:
    """
    Return canonical in-situ observations snapshot matching the VARUNA /observations contract.
    Directly consumed by Person 1's Graph Fusion Engine and Person 5's Backend Gateway.
    """
    global _latest_snapshot, _latest_profiles, _latest_qc_report

    bounds = None
    if all(v is not None for v in (lat_min, lat_max, lon_min, lon_max)):
        bounds = RegionBounds(
            lat_min=lat_min,  # type: ignore[arg-type]
            lat_max=lat_max,  # type: ignore[arg-type]
            lon_min=lon_min,  # type: ignore[arg-type]
            lon_max=lon_max,  # type: ignore[arg-type]
            name=settings.region_name,
        )

    snapshot, profiles, qc_report = pipeline.run(bounds=bounds, source=source)
    _latest_snapshot = snapshot
    _latest_profiles = profiles
    _latest_qc_report = qc_report

    return snapshot


@app.get("/profiles", response_model=list[VerticalProfile])
async def get_profiles(
    source: str | None = Query(None, description="Override source adapter"),
) -> list[VerticalProfile]:
    """
    Return 3D depth profiles for Argo, Glider, and CTD platforms.
    """
    global _latest_profiles
    if _latest_profiles is None:
        _, profiles, _ = pipeline.run(source=source)
        _latest_profiles = profiles
    return _latest_profiles


@app.get("/qc-report", response_model=QualityControlReport)
async def get_qc_report() -> QualityControlReport:
    """Return quality control and sanitization report from latest pipeline execution."""
    global _latest_qc_report
    if _latest_qc_report is None:
        _, _, qc = pipeline.run()
        _latest_qc_report = qc
    return _latest_qc_report


def run_server():
    """Run uvicorn server directly."""
    import uvicorn
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)


if __name__ == "__main__":
    run_server()
