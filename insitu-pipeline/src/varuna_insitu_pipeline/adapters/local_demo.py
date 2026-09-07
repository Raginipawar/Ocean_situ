"""
Deterministic Local Demo Adapter for the Bay of Bengal.

Provides a scientifically grounded, deterministic set of real-world marine
observation platforms deployed in the Bay of Bengal:
- Argo profiling floats (WMO 2902698, 2902701, 2903345, 2903412, etc.)
- NIOT OMNI Moored Buoys (BD08, BD09, BD10, BD11, BD13, BD14)
- RAMA Research Buoy Network (15N, 12N, 8N on 90E)
- Coastal/Shelf Glider Transects
- Shipborne CTD hydrographic casts

Guarantees 100% reliable, zero-latency execution during judging or offline
rehearsals, with zero external network dependencies.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from ..schemas import RegionBounds, SensorType
from .base import BaseSensorAdapter, RawObservationRecord
from .registry import register_adapter

logger = logging.getLogger("varuna.insitu.local_demo")


from typing import Any

# Realistic locations of Moored Buoys in the Bay of Bengal (NIOT / RAMA)
BOB_MOORED_BUOYS: list[dict[str, Any]] = [
    {"id": "niot-bd08", "type": SensorType.BUOY, "lat": 18.2, "lon": 89.7, "name": "NIOT OMNI BD08"},
    {"id": "niot-bd09", "type": SensorType.BUOY, "lat": 17.5, "lon": 89.2, "name": "NIOT OMNI BD09"},
    {"id": "niot-bd10", "type": SensorType.BUOY, "lat": 16.5, "lon": 88.0, "name": "NIOT OMNI BD10"},
    {"id": "niot-bd11", "type": SensorType.BUOY, "lat": 14.0, "lon": 83.0, "name": "NIOT OMNI BD11"},
    {"id": "niot-bd13", "type": SensorType.BUOY, "lat": 11.0, "lon": 86.5, "name": "NIOT OMNI BD13"},
    {"id": "niot-bd14", "type": SensorType.BUOY, "lat": 7.0, "lon": 88.0, "name": "NIOT OMNI BD14"},
    {"id": "rama-15n90e", "type": SensorType.MOORING, "lat": 15.0, "lon": 90.0, "name": "RAMA 15N 90E"},
    {"id": "rama-12n90e", "type": SensorType.MOORING, "lat": 12.0, "lon": 90.0, "name": "RAMA 12N 90E"},
    {"id": "rama-08n90e", "type": SensorType.MOORING, "lat": 8.0, "lon": 90.0, "name": "RAMA 8N 90E"},
]

# Real Argo float positions active in the Bay of Bengal
BOB_ARGO_FLOATS: list[dict[str, Any]] = [
    {"id": "argo-2902698", "type": SensorType.ARGO, "lat": 13.25, "lon": 86.42},
    {"id": "argo-2902701", "type": SensorType.ARGO, "lat": 15.82, "lon": 89.15},
    {"id": "argo-2903345", "type": SensorType.ARGO, "lat": 11.45, "lon": 91.30},
    {"id": "argo-2903412", "type": SensorType.ARGO, "lat": 13.05, "lon": 87.98},
    {"id": "argo-2903521", "type": SensorType.ARGO, "lat": 17.10, "lon": 85.80},
    {"id": "argo-2903650", "type": SensorType.ARGO, "lat": 19.30, "lon": 88.60},
    {"id": "argo-2903710", "type": SensorType.ARGO, "lat": 9.50, "lon": 84.75},
    {"id": "argo-2903820", "type": SensorType.ARGO, "lat": 8.20, "lon": 92.40},
    {"id": "argo-2903930", "type": SensorType.ARGO, "lat": 16.80, "lon": 91.50},
    {"id": "argo-2904010", "type": SensorType.ARGO, "lat": 14.70, "lon": 84.30},
    {"id": "argo-2904120", "type": SensorType.ARGO, "lat": 18.00, "lon": 92.10},
    {"id": "argo-2904230", "type": SensorType.ARGO, "lat": 10.80, "lon": 88.50},
]

# Ocean Gliders & CTD casts
BOB_GLIDERS_AND_CTD: list[dict[str, Any]] = [
    {"id": "glider-incois-01", "type": SensorType.GLIDER, "lat": 14.5, "lon": 82.8},
    {"id": "glider-incois-02", "type": SensorType.GLIDER, "lat": 16.2, "lon": 84.1},
    {"id": "glider-incois-03", "type": SensorType.GLIDER, "lat": 12.1, "lon": 81.5},
    {"id": "ctd-orv-sagar-01", "type": SensorType.CTD, "lat": 13.5, "lon": 80.9},
    {"id": "ctd-orv-sagar-02", "type": SensorType.CTD, "lat": 15.0, "lon": 82.5},
    {"id": "ctd-orv-sagar-03", "type": SensorType.CTD, "lat": 17.8, "lon": 84.9},
    {"id": "drifter-noaa-62001", "type": SensorType.DRIFTER, "lat": 11.8, "lon": 89.2},
    {"id": "drifter-noaa-62002", "type": SensorType.DRIFTER, "lat": 15.4, "lon": 92.7},
]


@register_adapter("local_demo")
class LocalDemoObservationAdapter(BaseSensorAdapter):
    """
    Adapter generating synthetic yet realistic in-situ observation data
    for the Bay of Bengal, strictly matching physical oceanographic dynamics.
    """

    def __init__(self, data_file: Path | None = None):
        self.data_file = data_file

    @property
    def adapter_name(self) -> str:
        return "local_demo"

    @property
    def supported_sensor_types(self) -> list[SensorType]:
        return [
            SensorType.ARGO,
            SensorType.BUOY,
            SensorType.MOORING,
            SensorType.GLIDER,
            SensorType.CTD,
            SensorType.DRIFTER,
        ]

    def _generate_synthetic_records(
        self,
        bounds: RegionBounds,
        timestamp: datetime,
        seed: int = 42,
    ) -> list[RawObservationRecord]:
        """Generate realistic oceanographic sensor records for the Bay of Bengal."""
        rng = np.random.default_rng(seed)
        records: list[RawObservationRecord] = []

        all_stations = BOB_MOORED_BUOYS + BOB_ARGO_FLOATS + BOB_GLIDERS_AND_CTD

        # Marine heatwave patch centered around (17.0 N, 92.0 E) matching Person 1's mock
        hw_center = (17.0, 92.0)
        hw_radius = 2.5
        hw_peak = 2.2

        for station in all_stations:
            lat: float = float(station["lat"])
            lon: float = float(station["lon"])

            if not bounds.contains(lat, lon):
                continue

            st_type: SensorType = station["type"]  # type: ignore[assignment]
            sensor_id: str = str(station["id"])

            # SST calculation: tropical warm pool with latitudinal gradient
            # and heatwave anomaly in north-east
            lat_grad = 29.8 - 0.25 * (lat - bounds.lat_min)
            r2 = (lat - hw_center[0]) ** 2 + (lon - hw_center[1]) ** 2
            hw_effect = hw_peak * np.exp(-r2 / (2 * hw_radius ** 2))
            noise = float(rng.normal(0, 0.15))
            sst = round(float(lat_grad + hw_effect + noise), 2)

            # Salinity: Northern Bay of Bengal is fresher (~28-31 PSU) due to Ganges/Brahmaputra
            # Southern BoB is more saline (~34-35 PSU)
            sal_grad = 34.5 - 0.35 * (lat - bounds.lat_min)
            sal_noise = float(rng.normal(0, 0.2))
            salinity = round(float(np.clip(sal_grad + sal_noise, 27.0, 36.5)), 2)

            # Currents: cyclonic gyre in central basin
            dy = lat - 14.0
            dx = lon - 88.0
            r = np.hypot(dx, dy) + 1e-5
            speed = 0.5 * np.exp(-r / 6.0)
            u_ms = round(float(-speed * dy / r + 0.08 + rng.normal(0, 0.02)), 3)
            v_ms = round(float(speed * dx / r + 0.04 + rng.normal(0, 0.02)), 3)

            # Wave height: buoys report wave heights, Argo floats generally do not
            if st_type in (SensorType.BUOY, SensorType.MOORING):
                wave_m = round(float(np.clip(1.2 + 0.3 * np.sin(lon) + rng.normal(0, 0.1), 0.3, 4.5)), 2)
            else:
                wave_m = None

            # Chlorophyll: higher near river deltas (high latitudes in BoB)
            chl_val = round(float(np.clip(0.2 + 0.18 * max(0.0, lat - 14.0) + rng.normal(0, 0.05), 0.05, 8.0)), 3)

            # Surface level (0m)
            records.append(
                RawObservationRecord(
                    source_adapter="local_demo",
                    sensor_id=sensor_id,
                    sensor_type=st_type,
                    raw_lat=lat,
                    raw_lon=lon,
                    raw_depth=0.0,
                    time=timestamp,
                    raw_sst=sst,
                    raw_salinity=salinity,
                    raw_current_u=u_ms,
                    raw_current_v=v_ms,
                    raw_wave_height=wave_m,
                    raw_chlorophyll=chl_val,
                    qc_flag=1,
                )
            )

            # If profiling sensor (Argo or Glider), add subsurface depth levels
            if st_type in (SensorType.ARGO, SensorType.GLIDER):
                for depth in [10.0, 25.0, 50.0, 100.0, 200.0]:
                    # Thermocline decay
                    sub_sst = round(float(sst - 0.06 * depth), 2)
                    sub_sal = round(float(salinity + 0.015 * depth), 2)
                    records.append(
                        RawObservationRecord(
                            source_adapter="local_demo",
                            sensor_id=sensor_id,
                            sensor_type=st_type,
                            raw_lat=lat,
                            raw_lon=lon,
                            raw_depth=depth,
                            time=timestamp,
                            raw_sst=sub_sst,
                            raw_salinity=sub_sal,
                            raw_current_u=round(u_ms * 0.7, 3),
                            raw_current_v=round(v_ms * 0.7, 3),
                            raw_wave_height=None,
                            raw_chlorophyll=round(chl_val * 0.4, 3) if depth < 60.0 else None,
                            qc_flag=1,
                        )
                    )

        return records

    def fetch_raw(
        self,
        bounds: RegionBounds,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[RawObservationRecord]:
        """Fetch raw records from local cache file if exists, else synthesize."""
        timestamp = end_time or datetime.now(timezone.utc)

        # Check if pre-cached JSON file exists
        if self.data_file and Path(self.data_file).is_file():
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    records = []
                    for item in data.get("records", []):
                        records.append(RawObservationRecord(**item))
                    logger.info("Loaded %d records from demo cache file", len(records))
                    return records
            except (OSError, ValueError, TypeError) as exc:
                logger.warning("Failed to load demo cache file (%s); regenerating synthetically", exc)

        return self._generate_synthetic_records(bounds, timestamp)
