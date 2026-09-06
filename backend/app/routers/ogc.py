"""
VARUNA Backend — OGC Open Standards Layer.

Implements WMS and WCS endpoints for interoperability with standard
GIS tools (QGIS, ArcGIS, OpenLayers, etc.).

Endpoints:
    GET /ogc/wms  → WMS GetCapabilities + GetMap
    GET /ogc/wcs  → WCS GetCapabilities + GetCoverage

Note: This is a simplified OGC implementation for the SIH demo.
It supports the core operations needed for interoperability without
full OGC spec compliance.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from xml.etree.ElementTree import Element, SubElement, tostring

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from ..config import get_settings
from ..services.cf_metadata import VARIABLE_CF_METADATA
from ..services.ogc_renderer import LAYER_CONFIGS, render_map_tile

logger = logging.getLogger("varuna.ogc")

router = APIRouter(prefix="/ogc", tags=["OGC Standards"])


# ── WMS ──────────────────────────────────────────────────────────────

def _build_wms_capabilities() -> bytes:
    """Build a WMS 1.3.0 GetCapabilities XML document."""
    settings = get_settings()

    root = Element("WMS_Capabilities", {
        "version": "1.3.0",
        "xmlns": "http://www.opengis.net/wms",
        "xmlns:xlink": "http://www.w3.org/1999/xlink",
    })

    # Service metadata
    service = SubElement(root, "Service")
    SubElement(service, "Name").text = "WMS"
    SubElement(service, "Title").text = settings.ogc_title
    SubElement(service, "Abstract").text = settings.ogc_abstract

    # Capability
    capability = SubElement(root, "Capability")

    # Request operations
    request_el = SubElement(capability, "Request")

    for op_name in ("GetCapabilities", "GetMap"):
        op = SubElement(request_el, op_name)
        fmt = SubElement(op, "Format")
        fmt.text = "image/png" if op_name == "GetMap" else "text/xml"

    # Layer list
    parent_layer = SubElement(capability, "Layer")
    SubElement(parent_layer, "Title").text = "VARUNA Ocean Layers"

    crs = SubElement(parent_layer, "CRS")
    crs.text = "EPSG:4326"

    bbox = SubElement(parent_layer, "EX_GeographicBoundingBox")
    SubElement(bbox, "westBoundLongitude").text = str(settings.ogc_bbox_lon_min)
    SubElement(bbox, "eastBoundLongitude").text = str(settings.ogc_bbox_lon_max)
    SubElement(bbox, "southBoundLatitude").text = str(settings.ogc_bbox_lat_min)
    SubElement(bbox, "northBoundLatitude").text = str(settings.ogc_bbox_lat_max)

    for name, (cmap, label, vmin, vmax) in LAYER_CONFIGS.items():
        layer = SubElement(parent_layer, "Layer", {"queryable": "1"})
        SubElement(layer, "Name").text = name
        SubElement(layer, "Title").text = label
        SubElement(layer, "Abstract").text = f"VARUNA fused {label} layer (colormap: {cmap})"

    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(root, encoding="unicode").encode("utf-8")


@router.get("/wms")
async def wms(
    request: Request,
    SERVICE: str = Query("WMS"),
    REQUEST: str = Query("GetCapabilities"),
    LAYERS: str | None = Query(None),
    BBOX: str | None = Query(None),
    WIDTH: int = Query(512),
    HEIGHT: int = Query(512),
    FORMAT: str = Query("image/png"),
    CRS: str = Query("EPSG:4326"),
) -> Response:
    """
    OGC WMS endpoint.

    Supports:
    - GetCapabilities: returns XML service description
    - GetMap: returns a rendered map tile as PNG
    """
    if REQUEST.upper() == "GETCAPABILITIES":
        xml_bytes = _build_wms_capabilities()
        return Response(content=xml_bytes, media_type="text/xml")

    if REQUEST.upper() == "GETMAP":
        if not LAYERS:
            raise HTTPException(status_code=400, detail="LAYERS parameter required")
        if not BBOX:
            raise HTTPException(status_code=400, detail="BBOX parameter required")

        # Parse BBOX (lon_min,lat_min,lon_max,lat_max)
        try:
            parts = [float(x.strip()) for x in BBOX.split(",")]
            if len(parts) != 4:
                raise ValueError
            bbox = (parts[0], parts[1], parts[2], parts[3])
        except (ValueError, IndexError):
            raise HTTPException(
                status_code=400,
                detail="BBOX must be lon_min,lat_min,lon_max,lat_max",
            )

        # Clamp dimensions
        WIDTH = min(max(WIDTH, 64), 2048)
        HEIGHT = min(max(HEIGHT, 64), 2048)

        # Fetch fused data from upstream
        try:
            upstream = request.app.state.upstream
            fused = await upstream.get_fused()
            points = fused.get("points", [])
        except Exception as exc:
            logger.error("Failed to fetch fused data for GetMap: %s", exc)
            raise HTTPException(status_code=502, detail=f"Upstream unavailable: {exc}") from exc

        # Render the first requested layer
        layer = LAYERS.split(",")[0].strip().lower()

        try:
            png_bytes = render_map_tile(points, layer, bbox, WIDTH, HEIGHT)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.error("Map rendering failed: %s", exc)
            raise HTTPException(status_code=500, detail=f"Rendering failed: {exc}") from exc

        return Response(content=png_bytes, media_type="image/png")

    raise HTTPException(status_code=400, detail=f"Unsupported REQUEST: {REQUEST}")


# ── WCS ──────────────────────────────────────────────────────────────

def _build_wcs_capabilities() -> bytes:
    """Build a WCS 2.0 GetCapabilities XML document."""
    settings = get_settings()

    root = Element("Capabilities", {
        "version": "2.0.1",
        "xmlns": "http://www.opengis.net/wcs/2.0",
    })

    # Service identification
    si = SubElement(root, "ServiceIdentification")
    SubElement(si, "Title").text = settings.ogc_title
    SubElement(si, "Abstract").text = settings.ogc_abstract
    SubElement(si, "ServiceType").text = "WCS"
    SubElement(si, "ServiceTypeVersion").text = "2.0.1"

    # Contents
    contents = SubElement(root, "Contents")

    coverages = ["sst_c", "current_u_ms", "current_v_ms", "wave_height_m"]
    for cov_id in coverages:
        cf = VARIABLE_CF_METADATA.get(cov_id)
        summary = SubElement(contents, "CoverageSummary")
        SubElement(summary, "CoverageId").text = cov_id
        SubElement(summary, "CoverageSubtype").text = "RectifiedGridCoverage"
        if cf:
            SubElement(summary, "Title").text = cf.long_name

    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(root, encoding="unicode").encode("utf-8")


@router.get("/wcs")
async def wcs(
    request: Request,
    SERVICE: str = Query("WCS"),
    REQUEST: str = Query("GetCapabilities"),
    COVERAGEID: str | None = Query(None, alias="CoverageId"),
    BBOX: str | None = Query(None),
    FORMAT: str = Query("application/json"),
) -> Response:
    """
    OGC WCS endpoint.

    Supports:
    - GetCapabilities: returns XML service description
    - GetCoverage: returns gridded data as JSON with CF metadata
    """
    if REQUEST.upper() == "GETCAPABILITIES":
        xml_bytes = _build_wcs_capabilities()
        return Response(content=xml_bytes, media_type="text/xml")

    if REQUEST.upper() == "GETCOVERAGE":
        if not COVERAGEID:
            raise HTTPException(status_code=400, detail="CoverageId parameter required")

        # Fetch fused data
        try:
            upstream = request.app.state.upstream
            fused = await upstream.get_fused()
            points = fused.get("points", [])
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Upstream unavailable: {exc}") from exc

        # Filter by BBOX if provided
        if BBOX:
            try:
                lon_min, lat_min, lon_max, lat_max = [float(x) for x in BBOX.split(",")]
                points = [
                    p for p in points
                    if (lat_min <= p.get("lat", 0) <= lat_max and
                        lon_min <= p.get("lon", 0) <= lon_max)
                ]
            except (ValueError, IndexError):
                raise HTTPException(status_code=400, detail="Invalid BBOX format")

        # Extract the requested variable
        values = []
        for pt in points:
            val = pt.get(COVERAGEID)
            values.append({
                "lat": pt.get("lat"),
                "lon": pt.get("lon"),
                "value": val,
            })

        # Add CF metadata
        cf = VARIABLE_CF_METADATA.get(COVERAGEID, None)
        cf_meta = cf.model_dump() if cf else {}

        import json
        result = {
            "coverageId": COVERAGEID,
            "time": fused.get("time"),
            "region": fused.get("region"),
            "cf_metadata": cf_meta,
            "values": values,
        }

        return Response(
            content=json.dumps(result, default=str),
            media_type="application/json",
        )

    raise HTTPException(status_code=400, detail=f"Unsupported REQUEST: {REQUEST}")
