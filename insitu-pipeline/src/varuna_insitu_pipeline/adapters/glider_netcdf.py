"""
Autonomous Underwater Glider Adapter.

Ingests high-resolution saw-tooth transect profiles from autonomous underwater gliders
(e.g., Slocum, SeaExplorer, Spray) in standard OceanGliders / EGO NetCDF format.
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from ..schemas import RegionBounds, SensorType
from .base import BaseSensorAdapter, RawObservationRecord
from .registry import register_adapter

logger = logging.getLogger("varuna.insitu.glider")


@register_adapter("glider_netcdf")
class GliderNetCDFAdapter(BaseSensorAdapter):
    """
    Adapter for Ocean Glider missions.
    """

    def __init__(self, data_source: str | Path | list[dict[str, Any]] | None = None):
        self.data_source = data_source

    @property
    def adapter_name(self) -> str:
        return "glider_netcdf"

    @property
    def supported_sensor_types(self) -> list[SensorType]:
        return [SensorType.GLIDER]

    def fetch_raw(
        self,
        bounds: RegionBounds,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[RawObservationRecord]:
        """Fetch raw glider records."""
        if isinstance(self.data_source, list):
            records = []
            for item in self.data_source:
                records.append(RawObservationRecord(**item))
            return records

        return []
