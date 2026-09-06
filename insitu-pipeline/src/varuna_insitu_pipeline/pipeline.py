"""
VARUNA In-Situ Observation Pipeline Orchestrator.

Coordinates ingestion across multiple sensor adapters, executes quality control,
sanitization, spatiotemporal bounding, and produces:
1. Canonical ObservationSnapshot for the /observations contract (Person 1 & Person 5).
2. VerticalProfile list for 3D depth-resolved profile views.
3. Detailed QualityControlReport.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from .adapters.base import BaseSensorAdapter
from .adapters.registry import AdapterRegistry
from .config import InSituSettings
from .config import settings as default_settings
from .processing.depth import build_vertical_profiles, extract_surface_snapshot
from .schemas import (
    ObservationPoint,
    ObservationSnapshot,
    QualityControlReport,
    RegionBounds,
    VerticalProfile,
)

logger = logging.getLogger("varuna.insitu.pipeline")


class InSituPipeline:
    """
    Main pipeline engine orchestrating in-situ observation ingestion.
    """

    def __init__(self, config: InSituSettings | None = None):
        self.config = config or default_settings

    def _resolve_adapters(self, source_override: str | None = None) -> list[BaseSensorAdapter]:
        """Resolve which adapters to run based on config or runtime override."""
        mode = (source_override or self.config.active_source).lower()

        adapters: list[BaseSensorAdapter] = []

        if mode == "composite":
            for name in self.config.enabled_adapters:
                try:
                    adapters.append(AdapterRegistry.instantiate(name))
                except KeyError:
                    logger.warning("Configured adapter '%s' not registered; skipping", name)
        else:
            try:
                adapters.append(AdapterRegistry.instantiate(mode))
            except KeyError:
                logger.warning("Requested adapter '%s' not found. Falling back to 'local_demo'", mode)
                adapters.append(AdapterRegistry.instantiate("local_demo"))

        return adapters

    def run(
        self,
        bounds: RegionBounds | None = None,
        source: str | None = None,
        timestamp: datetime | None = None,
    ) -> tuple[ObservationSnapshot, list[VerticalProfile], QualityControlReport]:
        """
        Execute the pipeline:
        1. Fetch raw observations across resolved adapters.
        2. Clean, sanitize, and validate coordinates & measurements.
        3. Extract surface snapshot for 2D fusion.
        4. Group multi-depth points into vertical profiles.
        5. Return canonical ObservationSnapshot, vertical profiles, and QC report.
        """
        start_time = time.perf_counter()
        target_bounds = bounds or self.config.bounds
        snapshot_time = timestamp or datetime.now(timezone.utc)

        adapters = self._resolve_adapters(source)
        all_cleaned_points: list[ObservationPoint] = []

        combined_report = QualityControlReport(
            source="+".join(a.adapter_name for a in adapters),
        )

        for adapter in adapters:
            try:
                points, report = adapter.get_observations(
                    bounds=target_bounds,
                    start_time=None,
                    end_time=snapshot_time,
                )
                all_cleaned_points.extend(points)
                combined_report.total_raw_records += report.total_raw_records
                combined_report.retained_records += report.retained_records
                combined_report.dropped_out_of_bounds += report.dropped_out_of_bounds
                combined_report.dropped_bad_qc += report.dropped_bad_qc
                combined_report.dropped_sentinels += report.dropped_sentinels
            except (RuntimeError, ValueError, OSError, KeyError) as exc:
                logger.error("Adapter '%s' execution failed: %s", adapter.adapter_name, exc)

        # Fallback to local_demo if all remote sources failed or returned 0 points
        if not all_cleaned_points and adapters and adapters[0].adapter_name != "local_demo":
            logger.warning("Remote adapters returned 0 points. Executing graceful fallback to local_demo.")
            fallback_adapter = AdapterRegistry.instantiate("local_demo")
            fb_points, _ = fallback_adapter.get_observations(
                bounds=target_bounds,
                start_time=None,
                end_time=snapshot_time,
            )
            all_cleaned_points.extend(fb_points)
            combined_report.source += "+fallback_local_demo"
            combined_report.retained_records += len(fb_points)

        # Extract 2D surface snapshot (shallowest valid level per sensor)
        surface_points = extract_surface_snapshot(
            all_cleaned_points,
            max_surface_depth_m=self.config.surface_max_depth_m,
        )

        # Build vertical profiles from all depths
        profiles = build_vertical_profiles(all_cleaned_points)

        combined_report.execution_time_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        snapshot = ObservationSnapshot(
            region=target_bounds.name,
            time=snapshot_time,
            source=combined_report.source,
            points=surface_points,
        )

        return snapshot, profiles, combined_report

    def get_snapshot(
        self,
        bounds: RegionBounds | None = None,
        source: str | None = None,
    ) -> ObservationSnapshot:
        """Convenience method returning just the canonical ObservationSnapshot."""
        snapshot, _, _ = self.run(bounds=bounds, source=source)
        return snapshot
