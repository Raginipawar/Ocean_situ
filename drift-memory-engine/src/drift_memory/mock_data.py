"""
Mock Data Generator for Drift Memory Engine.

Generates realistic Bay of Bengal oceanographic model grids and sensor
observations for Day 1-2 independent testing before live upstream connection.
"""
from __future__ import annotations

import math
import random
from datetime import datetime, timezone

from .schemas import (
    ModelGridPoint,
    ModelSnapshot,
    ObservationPoint,
    ObservationSnapshot,
    SensorType,
)


def generate_mock_model(
    time: datetime | None = None,
    resolution_deg: float = 1.0,
    seed: int = 42,
) -> ModelSnapshot:
    """Generate regular 1-degree grid across the Bay of Bengal."""
    rnd = random.Random(seed)
    now = time or datetime.now(timezone.utc)
    points: list[ModelGridPoint] = []

    # Bay of Bengal bounding box
    lats = [float(lat) for lat in range(6, 22, int(resolution_deg))]
    lons = [float(lon) for lon in range(81, 95, int(resolution_deg))]

    for lat in lats:
        for lon in lons:
            # Realistic spatial gradient: warmer south, slightly cooler north
            base_sst = 29.5 - (lat - 6.0) * 0.12 + rnd.uniform(-0.15, 0.15)
            # Cyclonic gyre circulation
            u = -0.25 * math.sin(math.radians(lat * 10.0)) + rnd.uniform(-0.05, 0.05)
            v = 0.20 * math.cos(math.radians(lon * 8.0)) + rnd.uniform(-0.05, 0.05)
            wave = 1.2 + 0.05 * (lat - 6.0) + rnd.uniform(-0.1, 0.1)

            points.append(
                ModelGridPoint(
                    lat=lat,
                    lon=lon,
                    depth_m=0.0,
                    sst_c=round(base_sst, 2),
                    current_u_ms=round(u, 2),
                    current_v_ms=round(v, 2),
                    wave_height_m=round(wave, 2),
                    salinity_psu=33.5,
                )
            )

    return ModelSnapshot(
        region="bay_of_bengal",
        time=now,
        resolution_deg=resolution_deg,
        source="mock_roms_grid",
        points=points,
    )


def generate_mock_observations(
    time: datetime | None = None,
    n_argo: int = 8,
    n_buoy: int = 6,
    seed: int = 42,
) -> ObservationSnapshot:
    """Generate realistic sparse in-situ observations at known mooring/drifter sites."""
    rnd = random.Random(seed)
    now = time or datetime.now(timezone.utc)
    points: list[ObservationPoint] = []

    # Pre-defined known Indian Ocean mooring / buoy coordinates
    buoy_sites = [
        ("BD08", 18.2, 89.7),
        ("BD09", 17.5, 89.2),
        ("BD10", 16.3, 88.0),
        ("BD11", 14.0, 83.0),
        ("BD12", 11.5, 86.0),
        ("BD13", 14.0, 87.0),
        ("BD14", 8.0, 85.5),
        ("CB01", 11.0, 80.5),
    ]

    for sensor_id, lat, lon in buoy_sites[:n_buoy]:
        base_sst = 29.5 - (lat - 6.0) * 0.12 + rnd.uniform(-0.1, 0.1)
        u = -0.25 * math.sin(math.radians(lat * 10.0)) + rnd.uniform(-0.04, 0.04)
        v = 0.20 * math.cos(math.radians(lon * 8.0)) + rnd.uniform(-0.04, 0.04)
        wave = 1.2 + 0.05 * (lat - 6.0) + rnd.uniform(-0.08, 0.08)

        points.append(
            ObservationPoint(
                sensor_id=f"buoy-{sensor_id}",
                sensor_type=SensorType.buoy,
                lat=lat,
                lon=lon,
                depth_m=0.0,
                time=now,
                sst_c=round(base_sst, 2),
                current_u_ms=round(u, 2),
                current_v_ms=round(v, 2),
                wave_height_m=round(wave, 2),
                salinity_psu=33.6,
            )
        )

    # Argo float positions
    for i in range(n_argo):
        lat = round(rnd.uniform(8.0, 20.0), 2)
        lon = round(rnd.uniform(83.0, 93.0), 2)
        base_sst = 29.5 - (lat - 6.0) * 0.12 + rnd.uniform(-0.15, 0.15)
        points.append(
            ObservationPoint(
                sensor_id=f"argo-290{3400 + i}",
                sensor_type=SensorType.argo,
                lat=lat,
                lon=lon,
                depth_m=0.0,
                time=now,
                sst_c=round(base_sst, 2),
                current_u_ms=None,
                current_v_ms=None,
                wave_height_m=None,
                salinity_psu=34.0,
            )
        )

    return ObservationSnapshot(
        region="bay_of_bengal",
        time=now,
        source="mock_insitu_network",
        points=points,
    )
