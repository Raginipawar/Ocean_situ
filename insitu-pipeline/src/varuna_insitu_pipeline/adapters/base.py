"""
Abstract Base Class and data models for In-Situ Sensor Adapters.

Every physical observation platform (Argo, Glider, Buoy, CTD, ADCP, etc.)
implements this interface, enabling seamless plug-and-play addition of new
sensor platforms with zero modifications to downstream engines.
"""
from __future__ import annotations

import abc
import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from ..processing.qc import is_qc_acceptable
from ..processing.sanitize import clean_measurement
from ..processing.spatial import validate_coordinates
from ..schemas import ObservationPoint, QualityControlReport, RegionBounds, SensorType

logger = logging.getLogger("varuna.insitu.adapter")


class RawObservationRecord(BaseModel):
    """Normalized intermediate representation of a raw sensor reading."""
    source_adapter: str
    sensor_id: str
    sensor_type: SensorType
    raw_lat: Any
    raw_lon: Any
    raw_depth: Any = 0.0
    time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw_sst: Any = None
    raw_salinity: Any = None
    raw_current_u: Any = None
    raw_current_v: Any = None
    raw_wave_height: Any = None
    raw_chlorophyll: Any = None
    qc_flag: Any = 1
    metadata: dict[str, Any] = Field(default_factory=dict)


class BaseSensorAdapter(abc.ABC):
    """
    Abstract Sensor Adapter.
    Subclasses implement source-specific fetching and parsing.
    """

    @property
    @abc.abstractmethod
    def adapter_name(self) -> str:
        """Unique identifier for this adapter (e.g. 'argo_netcdf', 'argovis_api')."""
        ...

    @property
    @abc.abstractmethod
    def supported_sensor_types(self) -> list[SensorType]:
        """List of sensor platforms handled by this adapter."""
        ...

    @abc.abstractmethod
    def fetch_raw(
        self,
        bounds: RegionBounds,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[RawObservationRecord]:
        """
        Fetch or ingest raw data from file, network, or API.
        Must return a list of RawObservationRecord.
        """
        ...

    def parse_and_clean(
        self,
        raw_records: list[RawObservationRecord],
        bounds: RegionBounds,
        allowed_qc_flags: tuple[int, ...] = (1, 2),
        enforce_physical_limits: bool = True,
    ) -> tuple[list[ObservationPoint], QualityControlReport]:
        """
        Standard quality control, spatial bounding, and sanitization pass.
        Converts RawObservationRecord items into validated ObservationPoint items.
        """
        report = QualityControlReport(
            source=self.adapter_name,
            total_raw_records=len(raw_records),
        )

        cleaned_points: list[ObservationPoint] = []

        for rec in raw_records:
            # 1. Spatial validation & normalization
            coords = validate_coordinates(rec.raw_lat, rec.raw_lon)
            if coords is None:
                report.dropped_out_of_bounds += 1
                continue

            lat, lon = coords
            if not bounds.contains(lat, lon):
                report.dropped_out_of_bounds += 1
                continue

            # 2. Quality Control (QC) check
            if not is_qc_acceptable(rec.qc_flag, allowed_flags=allowed_qc_flags):
                report.dropped_bad_qc += 1
                continue

            # 3. Depth check
            try:
                depth_m = max(0.0, float(rec.raw_depth or 0.0))
            except (ValueError, TypeError):
                depth_m = 0.0

            # 4. Clean physical measurements
            sst = clean_measurement(rec.raw_sst, "sst_c", enforce_physical_limits)
            sal = clean_measurement(rec.raw_salinity, "salinity_psu", enforce_physical_limits)
            u = clean_measurement(rec.raw_current_u, "current_u_ms", enforce_physical_limits)
            v = clean_measurement(rec.raw_current_v, "current_v_ms", enforce_physical_limits)
            wave = clean_measurement(rec.raw_wave_height, "wave_height_m", enforce_physical_limits)
            chl = clean_measurement(rec.raw_chlorophyll, "chlorophyll_mg_m3", enforce_physical_limits)

            # Check if all values were sentinels/None
            if all(v is None for v in (sst, sal, u, v, wave, chl)):
                report.dropped_sentinels += 1
                continue

            point = ObservationPoint(
                sensor_id=rec.sensor_id,
                sensor_type=rec.sensor_type,
                lat=lat,
                lon=lon,
                depth_m=depth_m,
                time=rec.time,
                sst_c=sst,
                current_u_ms=u,
                current_v_ms=v,
                wave_height_m=wave,
                salinity_psu=sal,
                chlorophyll_mg_m3=chl,
            )
            cleaned_points.append(point)

        report.retained_records = len(cleaned_points)
        return cleaned_points, report

    def get_observations(
        self,
        bounds: RegionBounds,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> tuple[list[ObservationPoint], QualityControlReport]:
        """Fetch raw records and return sanitized, QC-validated observation points."""
        raw = self.fetch_raw(bounds, start_time, end_time)
        return self.parse_and_clean(raw, bounds)
