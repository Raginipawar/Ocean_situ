"""
Synthetic /model and /observations generators.

Real data ingestion is owned by Person 4 (Copernicus/HYCOM/INCOIS -> /model)
and Person 6 (Argo/Glider/CTD/Buoy -> /observations). This module produces
data of the *exact same shape* so the Graph Fusion Engine, its tests, the demo
script and the API are fully runnable standalone from Day 1, and become a
literal one-line swap (see adapters.py) once the real endpoints land on
Day 3.

Design of the simulated "gap between model and reality" (this is what the
fusion engine has to recover):

  truth(lat, lon)  = smooth base field + small-scale texture + a localised
                     "marine heatwave" anomaly patch
  model(lat, lon)  = smooth base field + small-scale texture   (NO heatwave,
                     plus a small independent coastal cold bias)

/model reports `model(...)`. /observations samples `truth(...)` at sparse
sensor locations (with realistic instrument noise), and a fraction of sensors
are deliberately placed inside the heatwave patch so the residual signal the
engine has to recover is real and locally large -- exactly the "model and
reality disagree" scenario VARUNA exists to surface.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

import numpy as np

from . import config
from .schemas import ModelGridPoint, ModelSnapshot, ObservationPoint, ObservationSnapshot, SensorType

# Centre of the synthetic marine-heatwave anomaly (purely for demo realism)
_HEATWAVE_CENTER = (17.0, 92.0)   # (lat, lon)
_HEATWAVE_RADIUS_DEG = 2.5
_HEATWAVE_PEAK_C = 2.2

# Centre of the synthetic mesoscale gyre driving the current field
_GYRE_CENTER = (13.0, 88.0)


def _base_sst(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    latitudinal = 29.5 - 0.33 * (lat - config.LAT_MIN)
    texture = 0.4 * np.sin(np.radians(lon) * 5.0) * np.cos(np.radians(lat) * 4.0)
    return latitudinal + texture


def _heatwave_patch(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    r2 = ((lat - _HEATWAVE_CENTER[0]) ** 2 + (lon - _HEATWAVE_CENTER[1]) ** 2)
    return _HEATWAVE_PEAK_C * np.exp(-r2 / (2 * _HEATWAVE_RADIUS_DEG ** 2))


def _coastal_cold_bias(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    # crude "coastline" proxy: model runs slightly cold near the western edge
    dist_from_west_edge = lon - config.LON_MIN
    return -0.6 * np.exp(-dist_from_west_edge / 4.0)


def _currents(lat: np.ndarray, lon: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    dy = lat - _GYRE_CENTER[0]
    dx = lon - _GYRE_CENTER[1]
    r = np.hypot(dx, dy) + 1e-6
    speed = 0.55 * np.exp(-r / 6.0)
    u = -speed * dy / r + 0.10   # counter-clockwise gyre + weak background eastward drift
    v = speed * dx / r + 0.03
    return u, v


def _wave_height(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    base = 1.1 + 0.35 * np.sin(np.radians(lon - config.LON_MIN) * 2.0)
    texture = 0.15 * np.cos(np.radians(lat) * 6.0)
    return np.clip(base + texture, 0.1, 4.0)


def truth_fields(lat: np.ndarray, lon: np.ndarray) -> dict[str, np.ndarray]:
    """The synthetic 'real ocean'. /observations samples this (plus noise)."""
    sst = _base_sst(lat, lon) + _heatwave_patch(lat, lon)
    u, v = _currents(lat, lon)
    wave = _wave_height(lat, lon)
    return {"sst_c": sst, "current_u_ms": u, "current_v_ms": v, "wave_height_m": wave}


def model_fields(lat: np.ndarray, lon: np.ndarray) -> dict[str, np.ndarray]:
    """The synthetic 'forecast model'. /model reports this. No heatwave signal."""
    sst = _base_sst(lat, lon) + _coastal_cold_bias(lat, lon)
    u, v = _currents(lat, lon)
    wave = _wave_height(lat, lon)
    return {"sst_c": sst, "current_u_ms": u, "current_v_ms": v, "wave_height_m": wave}


def generate_mock_model_grid(
    resolution_deg: float = config.GRID_RESOLUTION_DEG,
    timestamp: datetime | None = None,
) -> ModelSnapshot:
    timestamp = timestamp or datetime.now(timezone.utc)

    lats = np.arange(config.LAT_MIN, config.LAT_MAX + 1e-9, resolution_deg)
    lons = np.arange(config.LON_MIN, config.LON_MAX + 1e-9, resolution_deg)
    lat_grid, lon_grid = np.meshgrid(lats, lons, indexing="ij")
    lat_flat, lon_flat = lat_grid.ravel(), lon_grid.ravel()

    fields = model_fields(lat_flat, lon_flat)

    points = [
        ModelGridPoint(
            lat=float(lat_flat[i]),
            lon=float(lon_flat[i]),
            depth_m=0.0,
            sst_c=float(fields["sst_c"][i]),
            current_u_ms=float(fields["current_u_ms"][i]),
            current_v_ms=float(fields["current_v_ms"][i]),
            wave_height_m=float(fields["wave_height_m"][i]),
        )
        for i in range(len(lat_flat))
    ]

    return ModelSnapshot(
        region=config.REGION_NAME,
        time=timestamp,
        resolution_deg=resolution_deg,
        source="mock",
        points=points,
    )


def generate_mock_observations(
    n_sensors: int = 40,
    timestamp: datetime | None = None,
    seed: int = 7,
    heatwave_fraction: float = 0.25,
    noise_std: dict[str, float] | None = None,
) -> ObservationSnapshot:
    timestamp = timestamp or datetime.now(timezone.utc)
    rng = np.random.default_rng(seed)
    noise_std = noise_std or {
        "sst_c": 0.15,
        "current_u_ms": 0.03,
        "current_v_ms": 0.03,
        "wave_height_m": 0.08,
    }

    n_heatwave = max(1, int(round(n_sensors * heatwave_fraction)))
    n_random = n_sensors - n_heatwave

    hw_lat = rng.normal(_HEATWAVE_CENTER[0], _HEATWAVE_RADIUS_DEG * 0.5, n_heatwave)
    hw_lon = rng.normal(_HEATWAVE_CENTER[1], _HEATWAVE_RADIUS_DEG * 0.5, n_heatwave)

    rand_lat = rng.uniform(config.LAT_MIN, config.LAT_MAX, n_random)
    rand_lon = rng.uniform(config.LON_MIN, config.LON_MAX, n_random)

    lat = np.clip(np.concatenate([hw_lat, rand_lat]), config.LAT_MIN, config.LAT_MAX)
    lon = np.clip(np.concatenate([hw_lon, rand_lon]), config.LON_MIN, config.LON_MAX)
    rng.shuffle(lat)  # decouple index order from patch membership for realism
    rng.shuffle(lon)

    type_options = [SensorType.ARGO, SensorType.GLIDER, SensorType.CTD, SensorType.BUOY]
    type_idx = rng.choice(len(type_options), size=n_sensors, p=[0.35, 0.2, 0.2, 0.25])
    sensor_types = [type_options[i] for i in type_idx]
    # Argo/Glider profile to depth; CTD casts are shallow-to-mid; buoys are surface.
    depth_choices = {
        SensorType.ARGO: [0.0, 10.0, 50.0, 100.0],
        SensorType.GLIDER: [0.0, 10.0, 25.0],
        SensorType.CTD: [0.0, 10.0],
        SensorType.BUOY: [0.0],
    }
    depth_m = np.array([rng.choice(depth_choices[st]) for st in sensor_types])

    truth = truth_fields(lat, lon)

    points = []
    for i in range(n_sensors):
        points.append(
            ObservationPoint(
                sensor_id=f"{sensor_types[i].value}-{i:03d}",
                sensor_type=sensor_types[i],
                lat=float(lat[i]),
                lon=float(lon[i]),
                depth_m=float(depth_m[i]),
                time=timestamp,
                sst_c=float(truth["sst_c"][i] + rng.normal(0, noise_std["sst_c"])),
                current_u_ms=float(truth["current_u_ms"][i] + rng.normal(0, noise_std["current_u_ms"])),
                current_v_ms=float(truth["current_v_ms"][i] + rng.normal(0, noise_std["current_v_ms"])),
                wave_height_m=float(max(0.0, truth["wave_height_m"][i] + rng.normal(0, noise_std["wave_height_m"]))),
            )
        )

    return ObservationSnapshot(
        region=config.REGION_NAME,
        time=timestamp,
        source="mock",
        points=points,
    )
