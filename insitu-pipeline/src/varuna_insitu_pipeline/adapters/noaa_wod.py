"""
NOAA World Ocean Database (WOD) / CTD Cast Adapter.

Parses shipborne CTD, XBT, and Ocean Station Data (OSD) casts from NOAA WOD format.
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from ..schemas import RegionBounds, SensorType
from .base import BaseSensorAdapter, RawObservationRecord
from .registry import register_adapter

logger = logging.getLogger("varuna.insitu.noaa_wod")


@register_adapter("noaa_wod")
class NoaaWodAdapter(BaseSensorAdapter):
    """
    Adapter for NOAA World Ocean Database hydrographic casts.
    """

    def __init__(self, data_source: str | Path | list[dict[str, Any]] | None = None):
        self.data_source = data_source

    @property
    def adapter_name(self) -> str:
        return "noaa_wod"

    @property
    def supported_sensor_types(self) -> list[SensorType]:
        return [SensorType.CTD, SensorType.XBT]

    def fetch_raw(
        self,
        bounds: RegionBounds,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[RawObservationRecord]:
        """Fetch raw WOD records."""
        if isinstance(self.data_source, list):
            records = []
            for item in self.data_source:
                records.append(RawObservationRecord(**item))
            return records

        # Support CSV or JSON export from WOD
        if isinstance(self.data_source, (str, Path)):
            path = Path(self.data_source)
            if path.is_file() and path.suffix == ".json":
                import json
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    return [RawObservationRecord(**r) for r in data.get("records", [])]
                except (json.JSONDecodeError, OSError, ValueError) as exc:
                    logger.warning("Error reading WOD JSON file %s: %s", path, exc)

        return []
