"""
VARUNA Backend — Mock data service (Day 1–2 fallback).

Generates realistic Bay of Bengal oceanographic data when upstream
pipelines (Person 4's model, Person 6's observations) are not yet live.

This lets the frontend team build and test against real JSON shapes
without any dependency on upstream availability.

Data covers:
  - SST (sea surface temperature): 26–32 °C band typical of BoB
  - Currents (u/v): monsoon-influenced westward/southward drift
  - Wave height: 0.5–3.0 m typical swell
  - Observations: synthetic Argo float + buoy positions

Region: Bay of Bengal (lat 5–22°N, lon 80–100°E)
"""
from __future__ import annotations

import math
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any


# ── constants ─────────────────────────────────────────────────────────

REGION = "bay_of_bengal"

# Bounding box
LAT_MIN, LAT_MAX = 5.0, 22.0
LON_MIN, LON_MAX = 80.0, 100.0

# Grid resolution for model data (degrees)
GRID_RES = 1.0

# Sensor locations: (id, type, lat, lon)
_SENSOR_DEFS = [
    ("ARGO-6902905", "argo",    13.5, 87.2),
    ("ARGO-6903001", "argo",    10.1, 91.8),
    ("ARGO-6901234", "argo",    18.3, 85.5),
    ("ARGO-6900777", "argo",     8.7, 93.1),
    ("BUOY-BD08",    "buoy",    15.0, 88.0),
    ("BUOY-BD12",    "buoy",     9.5, 83.0),
    ("BUOY-BD15",    "buoy",    20.0, 90.5),
    ("MOOR-IND01",   "mooring", 12.0, 90.0),
    ("MOOR-IND02",   "mooring",  7.0, 80.5),
    ("DRIFTER-101",  "drifter", 16.5, 84.0),
    ("XBT-V45",      "xbt",     11.2, 92.4),
    ("GLIDER-G01",   "glider",  14.7, 86.3),
]


# ── helpers ──────────────────────────────────────────────────────────

def _seed(lat: float, lon: float, offset: int = 0) -> int:
    """Deterministic seed from lat/lon so data is stable between calls."""
    return int((lat * 1000 + lon * 100 + offset) % (2**31))


def _sst(lat: float, lon: float) -> float:
    """
    Synthetic SST: warmer in the south, slight east-west gradient,
    small random perturbation for realism.
    """
    rng = random.Random(_seed(lat, lon, 1))
    base = 32.0 - (lat - LAT_MIN) * 0.35 + (lon - LON_MIN) * 0.04
    noise = rng.gauss(0, 0.4)
    return round(min(max(base + noise, 24.0), 34.0), 2)


def _currents(lat: float, lon: float) -> tuple[float, float]:
    """
    Synthetic currents: monsoon-influenced.
    Northward Somali current influence in west, eastward equatorial jet.
    """
    rng = random.Random(_seed(lat, lon, 2))
    # Zonal (u): weak eastward / westward depending on lat band
    u = 0.15 * math.sin(math.radians((lat - 13) * 15)) + rng.gauss(0, 0.05)
    # Meridional (v): southward drift in northern BoB
    v = -0.1 * math.cos(math.radians((lat - 8) * 10)) + rng.gauss(0, 0.04)
    return round(u, 3), round(v, 3)


def _wave_height(lat: float, lon: float) -> float:
    """Synthetic wave height: higher in open ocean, calmer near coasts."""
    rng = random.Random(_seed(lat, lon, 3))
    base = 1.5 + 0.8 * math.cos(math.radians((lat - 12) * 8))
    noise = rng.gauss(0, 0.2)
    return round(max(0.3, base + noise), 2)


def _confidence(lat: float, lon: float, has_sensor_nearby: bool) -> float:
    """Confidence = 0.9 near sensors, 0.5–0.7 in sparse open ocean."""
    rng = random.Random(_seed(lat, lon, 4))
    base = 0.85 if has_sensor_nearby else 0.55
    return round(min(1.0, max(0.1, base + rng.gauss(0, 0.05))), 3)


def _trust_label(confidence: float) -> str:
    if confidence >= 0.75:
        return "green"
    if confidence >= 0.45:
        return "amber"
    return "red"


def _sensor_lats_lons() -> list[tuple[float, float]]:
    return [(lat, lon) for _, _, lat, lon in _SENSOR_DEFS]


def _near_sensor(lat: float, lon: float, threshold: float = 3.0) -> bool:
    for slat, slon in _sensor_lats_lons():
        if abs(lat - slat) < threshold and abs(lon - slon) < threshold:
            return True
    return False


# ── public API ───────────────────────────────────────────────────────

def generate_model_snapshot() -> dict[str, Any]:
    """
    Generate a ModelSnapshot covering the Bay of Bengal grid.

    Returns a dict matching the ModelSnapshot schema.
    """
    now = datetime.now(timezone.utc)
    points = []

    lat = LAT_MIN
    while lat <= LAT_MAX + 1e-6:
        lon = LON_MIN
        while lon <= LON_MAX + 1e-6:
            u, v = _currents(lat, lon)
            points.append({
                "lat": round(lat, 2),
                "lon": round(lon, 2),
                "depth_m": 0.0,
                "sst_c": _sst(lat, lon),
                "current_u_ms": u,
                "current_v_ms": v,
                "wave_height_m": _wave_height(lat, lon),
            })
            lon = round(lon + GRID_RES, 6)
        lat = round(lat + GRID_RES, 6)

    return {
        "region": REGION,
        "time": now.isoformat(),
        "resolution_deg": GRID_RES,
        "source": "mock",
        "points": points,
    }


def generate_observation_snapshot() -> dict[str, Any]:
    """
    Generate an ObservationSnapshot from synthetic Argo/buoy positions.

    Returns a dict matching the ObservationSnapshot schema.
    """
    now = datetime.now(timezone.utc)
    points = []

    for sensor_id, sensor_type, lat, lon in _SENSOR_DEFS:
        # Argo floats drift slightly each call for realism
        rng = random.Random(_seed(lat, lon, 99) + now.hour)
        d_lat = rng.gauss(0, 0.05) if sensor_type in ("argo", "drifter") else 0.0
        d_lon = rng.gauss(0, 0.05) if sensor_type in ("argo", "drifter") else 0.0
        obs_lat = round(lat + d_lat, 4)
        obs_lon = round(lon + d_lon, 4)

        # Observations close to but not identical to model values (bias)
        bias = rng.gauss(0, 0.3)
        obs_sst = round(_sst(obs_lat, obs_lon) + bias, 2)
        u, v = _currents(obs_lat, obs_lon)
        obs_u = round(u + rng.gauss(0, 0.02), 3)
        obs_v = round(v + rng.gauss(0, 0.02), 3)

        # Observation time: most sensors report slightly in the past
        obs_time = now - timedelta(minutes=rng.uniform(0, 45))

        point: dict[str, Any] = {
            "sensor_id": sensor_id,
            "sensor_type": sensor_type,
            "lat": obs_lat,
            "lon": obs_lon,
            "depth_m": 5.0 if sensor_type in ("argo", "glider") else 0.0,
            "time": obs_time.isoformat(),
            "sst_c": obs_sst,
            "current_u_ms": obs_u,
            "current_v_ms": obs_v,
            "wave_height_m": None,  # most in-situ sensors don't measure wave height
        }

        # Buoys and moorings do report wave height
        if sensor_type in ("buoy", "mooring"):
            point["wave_height_m"] = round(_wave_height(obs_lat, obs_lon) + rng.gauss(0, 0.1), 2)

        points.append(point)

    return {
        "region": REGION,
        "time": now.isoformat(),
        "source": "mock",
        "points": points,
    }


def generate_fused_snapshot(engine: str = "auto") -> dict[str, Any]:
    """
    Generate a FusedResponse combining model grid with observation corrections.

    Returns a dict matching the FusedResponse schema.
    """
    now = datetime.now(timezone.utc)
    model = generate_model_snapshot()
    obs = generate_observation_snapshot()

    # Build a fast sensor lookup {(round_lat, round_lon): obs_point}
    sensor_lookup: dict[tuple[float, float], dict] = {}
    for op in obs["points"]:
        key = (round(op["lat"], 0), round(op["lon"], 0))
        sensor_lookup[key] = op

    fused_points = []
    n_corrected = 0

    for gp in model["points"]:
        lat, lon = gp["lat"], gp["lon"]
        key = (round(lat, 0), round(lon, 0))
        near = _near_sensor(lat, lon)
        sensor_op = sensor_lookup.get(key)

        sst_model = gp["sst_c"]
        u_model = gp["current_u_ms"]
        v_model = gp["current_v_ms"]

        corr_sst = None
        corr_u = None
        corr_v = None
        is_sensor = False

        if sensor_op:
            corr_sst = round(sensor_op["sst_c"] - sst_model, 3) if sensor_op.get("sst_c") else None
            corr_u = round(sensor_op["current_u_ms"] - u_model, 3) if sensor_op.get("current_u_ms") else None
            corr_v = round(sensor_op["current_v_ms"] - v_model, 3) if sensor_op.get("current_v_ms") else None
            is_sensor = True
            n_corrected += 1

        confidence = _confidence(lat, lon, near)

        fused_points.append({
            "lat": lat,
            "lon": lon,
            "depth_m": 0.0,
            "sst_c": sst_model,
            "current_u_ms": u_model,
            "current_v_ms": v_model,
            "wave_height_m": gp["wave_height_m"],
            "correction_sst_c": corr_sst,
            "correction_current_u_ms": corr_u,
            "correction_current_v_ms": corr_v,
            "correction_wave_height_m": None,
            "confidence": confidence,
            "trust_label": _trust_label(confidence),
            "is_sensor_node": is_sensor,
            "support": round(min(1.0, confidence * 1.1), 3),
        })

    n_pts = len(fused_points)
    mean_conf = round(sum(p["confidence"] for p in fused_points) / n_pts, 4) if n_pts else 0.0

    return {
        "region": REGION,
        "time": now.isoformat(),
        "points": fused_points,
        "summary": {
            "engine": "fallback" if engine == "fallback" else "gnn",
            "n_sensors": len(_SENSOR_DEFS),
            "n_grid_points": n_pts,
            "n_graph_edges": n_corrected * 4,  # rough proxy
            "mean_confidence": mean_conf,
            "mean_abs_correction_sst_c": round(
                sum(abs(p["correction_sst_c"]) for p in fused_points if p["correction_sst_c"] is not None)
                / max(1, n_corrected),
                4,
            ),
            "validation_mae_sst_c": None,
            "runtime_ms": 12.0,
        },
    }


def generate_alerts(n_max: int = 5) -> list[dict[str, Any]]:
    """
    Generate a list of synthetic drift alerts.

    Alerts are deterministic per hour so they don't flicker every poll.
    """
    now = datetime.now(timezone.utc)
    seed_hour = int(now.strftime("%Y%m%d%H"))
    rng = random.Random(seed_hour)

    alert_templates = [
        {"variable": "sst_c",        "label": "SST",          "unit": "°C",  "threshold": 1.5},
        {"variable": "current_u_ms", "label": "Zonal Current","unit": "m/s", "threshold": 0.25},
        {"variable": "current_v_ms", "label": "Merid. Current","unit": "m/s","threshold": 0.25},
        {"variable": "wave_height_m","label": "Wave Height",  "unit": "m",   "threshold": 0.8},
    ]

    alerts = []
    n = rng.randint(1, min(n_max, len(alert_templates)))
    chosen = rng.sample(alert_templates, n)

    for tmpl in chosen:
        lat = round(rng.uniform(LAT_MIN + 1, LAT_MAX - 1), 2)
        lon = round(rng.uniform(LON_MIN + 1, LON_MAX - 1), 2)

        model_val = round(_sst(lat, lon) if tmpl["variable"] == "sst_c" else rng.uniform(0, 1), 2)
        divergence = round(tmpl["threshold"] + rng.uniform(0, 0.8), 2)
        observed_val = round(model_val + divergence * rng.choice([-1, 1]), 2)
        severity = "critical" if divergence > tmpl["threshold"] * 1.5 else "warning"

        alert_id = f"ALT-{seed_hour}-{tmpl['variable'][:3].upper()}"

        alerts.append({
            "id": alert_id,
            "region": REGION,
            "variable": tmpl["variable"],
            "severity": severity,
            "message": (
                f"Drift detected: Bay of Bengal, {tmpl['label']} diverging "
                f"{divergence:.1f}{tmpl['unit']} at ({lat}°N, {lon}°E)"
            ),
            "timestamp": now.isoformat(),
            "lat": lat,
            "lon": lon,
            "model_value": model_val,
            "observed_value": observed_val,
            "divergence": divergence,
        })

    return alerts
