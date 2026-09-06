"""Deterministic local/demo model source for offline pipeline execution."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import xarray as xr

from ..config import ModelPipelineSettings
from ..schema import CANONICAL_VARIABLES, ModelSource, validate_dataset_like
from ..errors import MissingVariableError


@dataclass(frozen=True)
class LocalDemoIngestionResult:
    """Standardized local demo source result."""

    dataset: xr.Dataset
    source: ModelSource = ModelSource.LOCAL_DEMO
    source_path: str | None = None
    coordinate_mapping: dict[str, str] | None = None
    variable_mapping: dict[str, str] | None = None
    warnings: list[str] | None = None


class LocalDemoSource:
    """Generate deterministic, scientifically plausible Bay of Bengal data."""

    def __init__(self, settings: ModelPipelineSettings | None = None) -> None:
        self.settings = settings or ModelPipelineSettings()

    def load(self) -> LocalDemoIngestionResult:
        cfg = self.settings
        # Slightly finer than the target grid so Checkpoint 7 exercises regridding.
        lat = np.arange(cfg.region.lat_min, cfg.region.lat_max + 1e-9, 0.5)
        lon = np.arange(cfg.region.lon_min, cfg.region.lon_max + 1e-9, 0.5)
        time = np.array(["2026-09-07T00:00:00"], dtype="datetime64[ns]")
        depth = np.array([0.0, 10.0])

        lon_grid, lat_grid = np.meshgrid(lon, lat)
        sst = 30.5 - 0.18 * (lat_grid - cfg.region.lat_min) + 0.02 * (lon_grid - cfg.region.lon_min)
        sst += 0.3 * np.sin(np.radians(lon_grid * 3.0))
        u = 0.12 + 0.04 * np.sin(np.radians(lat_grid * 8.0))
        v = -0.05 + 0.03 * np.cos(np.radians(lon_grid * 5.0))
        wave = 1.2 + 0.2 * np.sin(np.radians((lon_grid - cfg.region.lon_min) * 12.0))
        salinity_surface = 34.0 + 0.2 * np.cos(np.radians(lat_grid * 4.0))
        chlorophyll = 0.18 + 0.04 * np.exp(-((lat_grid - 17.0) ** 2 + (lon_grid - 91.0) ** 2) / 20.0)

        depth_stack = np.stack([np.zeros_like(sst), np.full_like(sst, 1.0)])
        u_depth = u[None, :, :] * (1.0 - 0.05 * depth_stack)
        v_depth = v[None, :, :] * (1.0 - 0.05 * depth_stack)
        salinity_depth = np.stack([salinity_surface, salinity_surface + 0.05])

        dataset = xr.Dataset(
            data_vars={
                "sst": (("time", "lat", "lon"), sst.reshape(1, len(lat), len(lon)), _attrs("sst")),
                "u_current": (("time", "depth", "lat", "lon"), u_depth.reshape(1, 2, len(lat), len(lon)), _attrs("u_current")),
                "v_current": (("time", "depth", "lat", "lon"), v_depth.reshape(1, 2, len(lat), len(lon)), _attrs("v_current")),
                "wave_height": (("time", "lat", "lon"), wave.reshape(1, len(lat), len(lon)), _attrs("wave_height")),
                "salinity": (("time", "depth", "lat", "lon"), salinity_depth.reshape(1, 2, len(lat), len(lon)), _attrs("salinity")),
                "chlorophyll": (("time", "lat", "lon"), chlorophyll.reshape(1, len(lat), len(lon)), _attrs("chlorophyll")),
            },
            coords={"time": time, "depth": depth, "lat": lat, "lon": lon},
            attrs={
                "source": ModelSource.LOCAL_DEMO.value,
                "source_url": None,
                "region": cfg.region.name,
                "processing_level": "local_demo_ingested",
                "target_resolution_deg": cfg.target_grid.resolution_deg,
                "history": "VARUNA model-pipeline: generated deterministic local demo dataset.",
            },
        )

        report = validate_dataset_like(dataset)
        if not report.ok:
            raise MissingVariableError(
                "Local demo dataset failed canonical schema validation: "
                + "; ".join(report.errors)
            )

        return LocalDemoIngestionResult(
            dataset=dataset,
            coordinate_mapping={"time": "time", "lat": "lat", "lon": "lon", "depth": "depth"},
            variable_mapping={name: name for name in CANONICAL_VARIABLES},
            warnings=report.warnings,
        )


def _attrs(name: str) -> dict[str, str]:
    spec = CANONICAL_VARIABLES[name]
    return {
        "units": spec.units,
        "standard_name": spec.standard_name,
        "long_name": spec.long_name,
        "source_variable": name,
    }
