"""
Moored Buoy Network Adapter.

Ingests surface metocean and subsurface ADCP data from moored buoy networks:
- NIOT OMNI (Ocean Mining Network Information) Buoys
- RAMA (Research Moored Array for African-Asian-Australian Monsoon Analysis)
- NDBC / INCOIS surface buoy feeds
"""
from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..schemas import RegionBounds, SensorType
from .base import BaseSensorAdapter, RawObservationRecord
from .registry import register_adapter

logger = logging.getLogger("varuna.insitu.buoy")


@register_adapter("buoy")
class BuoyObservationAdapter(BaseSensorAdapter):
    """
    Adapter for moored buoys (OMNI, RAMA, INCOIS).
    """

    def __init__(self, data_source: str | Path | list[dict[str, Any]] | None = None):
        self.data_source = data_source

    @property
    def adapter_name(self) -> str:
        return "buoy"

    @property
    def supported_sensor_types(self) -> list[SensorType]:
        return [SensorType.BUOY, SensorType.MOORING]

    def parse_buoy_csv(self, content: str) -> list[RawObservationRecord]:
        """Parse standard buoy CSV data."""
        records: list[RawObservationRecord] = []
        reader = csv.DictReader(io.StringIO(content))
        for row in reader:
            try:
                sensor_id = row.get("sensor_id", row.get("buoy_id", "buoy-unknown"))
                st_type_str = row.get("sensor_type", "buoy").lower()
                st_type = SensorType.MOORING if "mooring" in st_type_str else SensorType.BUOY

                lat = float(row["lat"])
                lon = float(row["lon"])
                depth_m = float(row.get("depth_m", 0.0))

                time_str = row.get("time", row.get("timestamp"))
                if time_str:
                    try:
                        time_dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                    except (ValueError, TypeError):
                        time_dt = datetime.now(timezone.utc)
                else:
                    time_dt = datetime.now(timezone.utc)

                sst = float(row["sst_c"]) if row.get("sst_c") not in (None, "", "null") else None
                sal = float(row["salinity_psu"]) if row.get("salinity_psu") not in (None, "", "null") else None
                u = float(row["current_u_ms"]) if row.get("current_u_ms") not in (None, "", "null") else None
                v = float(row["current_v_ms"]) if row.get("current_v_ms") not in (None, "", "null") else None
                wave = float(row["wave_height_m"]) if row.get("wave_height_m") not in (None, "", "null") else None
                qc = int(row.get("qc_flag", 1))

                records.append(
                    RawObservationRecord(
                        source_adapter="buoy",
                        sensor_id=sensor_id,
                        sensor_type=st_type,
                        raw_lat=lat,
                        raw_lon=lon,
                        raw_depth=depth_m,
                        time=time_dt,
                        raw_sst=sst,
                        raw_salinity=sal,
                        raw_current_u=u,
                        raw_current_v=v,
                        raw_wave_height=wave,
                        qc_flag=qc,
                    )
                )
            except (ValueError, KeyError, TypeError) as exc:
                logger.debug("Skipping invalid buoy CSV row (%s): %s", exc, row)

        return records

    def fetch_raw(
        self,
        bounds: RegionBounds,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[RawObservationRecord]:
        """Fetch raw buoy records."""
        if isinstance(self.data_source, list):
            # In-memory dictionary list
            records = []
            for item in self.data_source:
                records.append(RawObservationRecord(**item))
            return records

        if isinstance(self.data_source, (str, Path)):
            path = Path(self.data_source)
            if path.is_file():
                content = path.read_text(encoding="utf-8")
                return self.parse_buoy_csv(content)

        return []
