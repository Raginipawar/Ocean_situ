"""
Argovis REST API Adapter for real-time Argo profiling float data.

Queries the Argovis open API for Argo profile metadata and measurements
within the Bay of Bengal spatiotemporal bounding box.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from ..schemas import RegionBounds, SensorType
from .base import BaseSensorAdapter, RawObservationRecord
from .registry import register_adapter

logger = logging.getLogger("varuna.insitu.argovis")


@register_adapter("argovis")
class ArgovisRestAdapter(BaseSensorAdapter):
    """
    Adapter querying the Argovis REST API for Argo floats.
    """

    def __init__(
        self,
        api_base: str = "https://argovis-api.colorado.edu",
        api_key: str | None = None,
        timeout_s: float = 10.0,
    ):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.timeout_s = timeout_s

    @property
    def adapter_name(self) -> str:
        return "argovis"

    @property
    def supported_sensor_types(self) -> list[SensorType]:
        return [SensorType.ARGO]

    def _build_query_url(self, bounds: RegionBounds, start_time: datetime, end_time: datetime) -> str:
        """Construct the Argovis API URL with polygon box and date range."""
        start_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_str = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        polygon_str = f"[[{bounds.lon_min},{bounds.lat_min}],[{bounds.lon_max},{bounds.lat_min}],[{bounds.lon_max},{bounds.lat_max}],[{bounds.lon_min},{bounds.lat_max}],[{bounds.lon_min},{bounds.lat_min}]]"
        return f"{self.api_base}/argo?startDate={start_str}&endDate={end_str}&polygon={polygon_str}"

    def fetch_raw(
        self,
        bounds: RegionBounds,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[RawObservationRecord]:
        """Fetch profiles from Argovis API."""
        now = datetime.now(timezone.utc)
        end_dt = end_time or now
        start_dt = start_time or (end_dt - timedelta(days=14))

        url = self._build_query_url(bounds, start_dt, end_dt)
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["x-argokey"] = self.api_key

        records: list[RawObservationRecord] = []

        try:
            with httpx.Client(timeout=self.timeout_s) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    records = self._parse_argovis_json(data)
                    logger.info("Argovis API returned %d profiles", len(data))
                else:
                    logger.warning("Argovis API returned HTTP %d: %s", resp.status_code, resp.text[:200])
        except (httpx.HTTPError, OSError) as exc:
            logger.warning("Failed to connect to Argovis API (%s). Gracefully returning 0 records.", exc)

        return records

    def _parse_argovis_json(self, data: list[dict[str, Any]]) -> list[RawObservationRecord]:
        """Parse raw Argovis JSON items into RawObservationRecord items."""
        records: list[RawObservationRecord] = []

        for profile in data:
            profile_id = str(profile.get("_id", "unknown"))
            geolocation = profile.get("geolocation", {})
            coords = geolocation.get("coordinates", [])
            if len(coords) < 2:
                continue

            lon, lat = float(coords[0]), float(coords[1])
            timestamp_str = profile.get("timestamp")
            if timestamp_str:
                try:
                    time_dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    time_dt = datetime.now(timezone.utc)
            else:
                time_dt = datetime.now(timezone.utc)

            # Measurements array contains depth/pres, temp, psal
            measurements = profile.get("data", [])
            data_keys = profile.get("data_keys", [])

            pres_idx = data_keys.index("pres") if "pres" in data_keys else -1
            temp_idx = data_keys.index("temp") if "temp" in data_keys else -1
            psal_idx = data_keys.index("psal") if "psal" in data_keys else -1

            if not measurements:
                continue

            for level in measurements:
                depth_m = float(level[pres_idx]) if pres_idx >= 0 and pres_idx < len(level) else 0.0
                temp_c = float(level[temp_idx]) if temp_idx >= 0 and temp_idx < len(level) else None
                psal = float(level[psal_idx]) if psal_idx >= 0 and psal_idx < len(level) else None

                records.append(
                    RawObservationRecord(
                        source_adapter="argovis",
                        sensor_id=f"argo-{profile_id}",
                        sensor_type=SensorType.ARGO,
                        raw_lat=lat,
                        raw_lon=lon,
                        raw_depth=depth_m,
                        time=time_dt,
                        raw_sst=temp_c,
                        raw_salinity=psal,
                        qc_flag=1,
                    )
                )

        return records
