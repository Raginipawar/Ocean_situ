"""
VARUNA Backend — REST API router.

Proxies requests to upstream services (Person 1's Graph Fusion Engine,
and later Person 4/6's pipelines) and enriches responses with CF
Conventions metadata headers.

Endpoints:
    GET /api/model              → upstream /model
    GET /api/observations       → upstream /observations
    GET /api/fused              → upstream /fused  (native JSON)
    GET /api/fused/geojson      → fused data as GeoJSON FeatureCollection
    GET /api/alerts             → upstream /alerts (also used by drift memory engine)
    GET /api/health             → aggregated health check
    GET /api/cf-metadata        → CF Conventions variable metadata
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from ..services.cf_metadata import build_cf_headers, get_all_variable_metadata, get_global_metadata

logger = logging.getLogger("varuna.rest")

router = APIRouter(prefix="/api", tags=["REST API"])


def _upstream(request: Request):
    """Get the shared UpstreamClient from app state."""
    return request.app.state.upstream


@router.get("/health")
async def health(request: Request) -> dict:
    """
    Aggregated health check.

    Reports this gateway's status and the upstream graph fusion engine's
    status. Returns 200 even if upstream is down (with a degraded status)
    so load balancers don't kill the gateway.
    """
    result = {
        "status": "ok",
        "gateway": "varuna-backend",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "upstream": {},
    }
    try:
        upstream_health = await _upstream(request).get_health()
        result["upstream"]["graph_fusion"] = upstream_health
    except Exception as exc:
        result["upstream"]["graph_fusion"] = {"status": "unreachable", "error": str(exc)}
        result["status"] = "degraded"

    return result


@router.get("/model")
async def get_model(request: Request) -> JSONResponse:
    """Proxy to upstream /model endpoint."""
    try:
        data = await _upstream(request).get_model()
    except Exception as exc:
        logger.error("Failed to fetch /model: %s", exc)
        raise HTTPException(status_code=502, detail=f"Upstream /model unavailable: {exc}") from exc

    return JSONResponse(content=data, headers=build_cf_headers())


@router.get("/observations")
async def get_observations(request: Request) -> JSONResponse:
    """Proxy to upstream /observations endpoint."""
    try:
        data = await _upstream(request).get_observations()
    except Exception as exc:
        logger.error("Failed to fetch /observations: %s", exc)
        raise HTTPException(status_code=502, detail=f"Upstream /observations unavailable: {exc}") from exc

    return JSONResponse(content=data, headers=build_cf_headers())


@router.get("/fused")
async def get_fused(
    request: Request,
    engine: str = Query("auto", description="Engine to use: auto, gnn, or fallback"),
) -> JSONResponse:
    """Proxy to upstream /fused endpoint."""
    if engine not in ("auto", "gnn", "fallback"):
        raise HTTPException(status_code=400, detail=f"Invalid engine: {engine}")

    try:
        data = await _upstream(request).get_fused(engine=engine)
    except Exception as exc:
        logger.error("Failed to fetch /fused: %s", exc)
        raise HTTPException(status_code=502, detail=f"Upstream /fused unavailable: {exc}") from exc

    return JSONResponse(content=data, headers=build_cf_headers())


@router.get("/alerts")
async def get_alerts(request: Request) -> JSONResponse:
    """Proxy to upstream /alerts endpoint."""
    try:
        data = await _upstream(request).get_alerts()
    except Exception as exc:
        logger.error("Failed to fetch /alerts: %s", exc)
        raise HTTPException(status_code=502, detail=f"Upstream /alerts unavailable: {exc}") from exc

    return JSONResponse(content=data)


@router.get("/cf-metadata")
async def cf_metadata() -> dict:
    """
    Return CF Conventions metadata for all tracked variables.

    Useful for downstream tools that want to discover what variables
    are available and their standard names/units.
    """
    global_meta = get_global_metadata()
    variable_meta = get_all_variable_metadata()

    return {
        "global": global_meta.model_dump(),
        "variables": {k: v.model_dump() for k, v in variable_meta.items()},
    }


# ── GeoJSON helpers ───────────────────────────────────────────────────

def _trust_color(label: str) -> str:
    """Map trust label → hex color for CesiumJS entity styling."""
    return {"green": "#00e676", "amber": "#ffb300", "red": "#ff1744"}.get(label, "#90a4ae")


def _fused_to_geojson(fused: dict[str, Any]) -> dict[str, Any]:
    """
    Convert a FusedResponse dict into a valid GeoJSON FeatureCollection.

    Each fused grid point becomes a GeoJSON Point Feature. Properties carry:
      - All oceanographic fields (sst_c, currents, wave_height)
      - Correction deltas from the Graph Fusion Engine
      - confidence + trust_label for the frontend trust overlay
      - _color: precomputed hex so CesiumJS needn't re-derive it
      - _is_sensor: boolean flag for marker differentiation

    The FeatureCollection also carries top-level metadata in its
    ``varuna`` extension property (region, time, fusion summary).
    """
    points: list[dict] = fused.get("points", [])
    summary: dict = fused.get("summary", {})

    features: list[dict] = []
    for pt in points:
        lat = pt.get("lat")
        lon = pt.get("lon")
        if lat is None or lon is None:
            continue

        trust = pt.get("trust_label", "amber")
        feature: dict[str, Any] = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                # GeoJSON coordinate order is [lon, lat, depth]
                "coordinates": [lon, lat, -pt.get("depth_m", 0.0)],
            },
            "properties": {
                # ── oceanographic state ─────────────────────────
                "sst_c":          pt.get("sst_c"),
                "current_u_ms":   pt.get("current_u_ms"),
                "current_v_ms":   pt.get("current_v_ms"),
                "wave_height_m":  pt.get("wave_height_m"),
                # ── correction deltas (from Graph Fusion Engine) ─
                "correction_sst_c":         pt.get("correction_sst_c"),
                "correction_current_u_ms":  pt.get("correction_current_u_ms"),
                "correction_current_v_ms":  pt.get("correction_current_v_ms"),
                # ── trust overlay ───────────────────────────────
                "confidence":   pt.get("confidence", 1.0),
                "trust_label":  trust,
                "support":      pt.get("support", 0.0),
                # ── rendering hints for CesiumJS ────────────────
                "_color":       _trust_color(trust),
                "_is_sensor":   pt.get("is_sensor_node", False),
                # ── current vector magnitude (for arrow scaling) ─
                "_current_speed_ms": (
                    round(
                        (pt.get("current_u_ms") or 0.0) ** 2
                        + (pt.get("current_v_ms") or 0.0) ** 2,
                        4,
                    ) ** 0.5
                    if pt.get("current_u_ms") is not None else None
                ),
            },
        }
        features.append(feature)

    return {
        "type": "FeatureCollection",
        "features": features,
        # VARUNA extension: top-level metadata for the frontend
        "varuna": {
            "region":          fused.get("region", "bay_of_bengal"),
            "time":            fused.get("time"),
            "engine":          summary.get("engine"),
            "n_sensors":       summary.get("n_sensors", 0),
            "n_grid_points":   summary.get("n_grid_points", len(features)),
            "mean_confidence": summary.get("mean_confidence"),
            "runtime_ms":      summary.get("runtime_ms"),
        },
    }


@router.get("/fused/geojson", summary="Fused ocean state as GeoJSON FeatureCollection")
async def get_fused_geojson(
    request: Request,
    engine: str = Query(
        "auto",
        description="Fusion engine: auto | gnn | fallback",
    ),
    bbox: str | None = Query(
        None,
        description=(
            "Optional bounding box filter: lon_min,lat_min,lon_max,lat_max "
            "(EPSG:4326). E.g. 80,5,100,22 for the full Bay of Bengal."
        ),
    ),
) -> JSONResponse:
    """
    Return fused ocean-state data as a **GeoJSON FeatureCollection**.

    Each Point Feature represents one grid node from the Graph Fusion Engine
    (or mock fallback). Properties include all oceanographic variables plus
    the per-node ``confidence``, ``trust_label``, and ``_color`` fields
    needed by the CesiumJS trust overlay.

    Optionally filter the response to a bounding box with ``?bbox=``.

    CF Conventions metadata is returned in the ``X-CF-*`` response headers.
    """
    if engine not in ("auto", "gnn", "fallback"):
        raise HTTPException(status_code=400, detail=f"Invalid engine: {engine!r}")

    # Parse optional bbox filter
    bbox_filter: tuple[float, float, float, float] | None = None
    if bbox:
        try:
            parts = [float(x.strip()) for x in bbox.split(",")]
            if len(parts) != 4:
                raise ValueError("Expected 4 values")
            bbox_filter = (parts[0], parts[1], parts[2], parts[3])  # lon_min,lat_min,lon_max,lat_max
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid bbox '{bbox}': {exc}. Expected lon_min,lat_min,lon_max,lat_max",
            ) from exc

    # Fetch fused data (upstream → mock fallback)
    try:
        fused = await _upstream(request).get_fused(engine=engine)
    except Exception as exc:
        logger.error("Failed to fetch /fused for GeoJSON conversion: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"Upstream /fused unavailable: {exc}",
        ) from exc

    # Apply bounding-box pre-filter on raw points (before GeoJSON conversion)
    # This can significantly reduce response size for wide-area queries
    if bbox_filter:
        lon_min, lat_min, lon_max, lat_max = bbox_filter
        fused["points"] = [
            pt for pt in fused.get("points", [])
            if (
                lat_min <= (pt.get("lat") or 0.0) <= lat_max
                and lon_min <= (pt.get("lon") or 0.0) <= lon_max
            )
        ]
        logger.debug(
            "BBox filter [%.2f,%.2f,%.2f,%.2f] → %d points",
            lon_min, lat_min, lon_max, lat_max, len(fused["points"]),
        )

    geojson = _fused_to_geojson(fused)

    headers = {
        **build_cf_headers(),
        "Content-Type": "application/geo+json",
    }
    return JSONResponse(content=geojson, headers=headers)

