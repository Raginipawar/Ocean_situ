"""Common target grid generation for VARUNA model data."""

from __future__ import annotations

import numpy as np
import xarray as xr

from ..config import RegionBounds, TargetGridConfig


def build_target_grid(
    bounds: RegionBounds,
    config: TargetGridConfig,
) -> xr.Dataset:
    """Build the predictable common lat/lon target grid.

    The generated coordinates are boundary-inclusive when the configured
    resolution lands exactly on the boundary. Floating point noise is rounded so
    repeated runs generate identical coordinate values.
    """

    lat = _inclusive_range(bounds.lat_min, bounds.lat_max, config.resolution_deg)
    lon = _inclusive_range(bounds.lon_min, bounds.lon_max, config.resolution_deg)
    return xr.Dataset(
        coords={"lat": lat, "lon": lon},
        attrs={
            "region": bounds.name,
            "target_resolution_deg": config.resolution_deg,
            "target_grid_method": config.method,
            "target_lat_min": bounds.lat_min,
            "target_lat_max": bounds.lat_max,
            "target_lon_min": bounds.lon_min,
            "target_lon_max": bounds.lon_max,
        },
    )


def _inclusive_range(start: float, stop: float, step: float) -> np.ndarray:
    if step <= 0:
        raise ValueError("Grid resolution must be positive")
    count = int(np.floor((stop - start) / step + 1e-9)) + 1
    values = start + np.arange(count, dtype=float) * step
    if values.size == 0 or values[-1] < stop - 1e-9:
        values = np.append(values, stop)
    return np.round(values, 10)

