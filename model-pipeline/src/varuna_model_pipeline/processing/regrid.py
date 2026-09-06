"""Regrid canonical model datasets onto the common VARUNA target grid."""

from __future__ import annotations

import logging

import numpy as np
import xarray as xr

from ..config import RegionBounds, TargetGridConfig
from ..errors import MissingCoordinateError, MissingVariableError, ModelPipelineError
from ..schema import CANONICAL_VARIABLES
from .grid import build_target_grid
from .quality import validate_quality

logger = logging.getLogger(__name__)


class RegriddingError(ModelPipelineError):
    """Raised when common-grid regridding cannot be performed safely."""


def regrid_to_target(
    dataset: xr.Dataset,
    bounds: RegionBounds,
    target_config: TargetGridConfig,
    *,
    required_variables: tuple[str, ...] | None = None,
) -> xr.Dataset:
    """Interpolate a canonical Dataset onto the configured common lat/lon grid.

    Uses xarray's interpolation over `lat` and `lon` only, preserving time and
    depth dimensions when present. The configured method is `linear` or
    `nearest`; NaNs remain NaNs rather than being silently filled.
    """

    required = required_variables or tuple(CANONICAL_VARIABLES.keys())
    _validate_regrid_inputs(dataset, required)

    target = build_target_grid(bounds, target_config)
    target_lat = target.coords["lat"]
    target_lon = target.coords["lon"]

    working = _sort_spatial_coordinates(dataset)
    try:
        regridded = working.interp(
            lat=target_lat,
            lon=target_lon,
            method=target_config.method,
        )
    except Exception as exc:  # noqa: BLE001 - rewrap xarray/scipy details
        raise RegriddingError(f"Failed to regrid dataset: {exc}") from exc

    regridded.attrs = {
        **working.attrs,
        "target_resolution_deg": target_config.resolution_deg,
        "regridding_method": target_config.method,
        "processing_level": _append_processing_level(
            working.attrs.get("processing_level"), "regridded"
        ),
        "target_lat_min": bounds.lat_min,
        "target_lat_max": bounds.lat_max,
        "target_lon_min": bounds.lon_min,
        "target_lon_max": bounds.lon_max,
    }

    _validate_regridded_output(regridded, target_lat.values, target_lon.values, required)
    logger.info(
        "Regridded model dataset to %.4f degree grid (%d lat x %d lon)",
        target_config.resolution_deg,
        target_lat.size,
        target_lon.size,
    )
    return regridded


def _validate_regrid_inputs(dataset: xr.Dataset, required: tuple[str, ...]) -> None:
    for coord in ("lat", "lon"):
        if coord not in dataset.coords:
            raise MissingCoordinateError(f"Cannot regrid without coordinate {coord!r}")
        values = np.asarray(dataset[coord].values, dtype=float)
        if values.size < 2:
            raise RegriddingError(f"Coordinate {coord!r} needs at least two points for regridding")
        if np.unique(values).size != values.size:
            raise RegriddingError(f"Coordinate {coord!r} contains duplicate values")

    missing = [name for name in required if name not in dataset.data_vars]
    if missing:
        raise MissingVariableError(f"Cannot regrid missing required variable(s): {missing}")


def _sort_spatial_coordinates(dataset: xr.Dataset) -> xr.Dataset:
    out = dataset
    if np.any(np.diff(np.asarray(out["lat"].values, dtype=float)) < 0):
        out = out.sortby("lat")
    if np.any(np.diff(np.asarray(out["lon"].values, dtype=float)) < 0):
        out = out.sortby("lon")
    return out


def _validate_regridded_output(
    dataset: xr.Dataset,
    expected_lat: np.ndarray,
    expected_lon: np.ndarray,
    required: tuple[str, ...],
) -> None:
    if not np.array_equal(np.asarray(dataset["lat"].values), expected_lat):
        raise RegriddingError("Regridded latitude coordinate does not match target grid")
    if not np.array_equal(np.asarray(dataset["lon"].values), expected_lon):
        raise RegriddingError("Regridded longitude coordinate does not match target grid")

    for name in required:
        if name not in dataset.data_vars:
            raise MissingVariableError(f"Regridded output missing variable {name!r}")
        dims = set(dataset[name].dims)
        if not {"lat", "lon"}.issubset(dims):
            raise RegriddingError(f"{name}: regridded variable lacks lat/lon dimensions")

    report = validate_quality(dataset, required_variables=required, max_nan_fraction=0.95)
    hard_errors = [
        issue
        for issue in report.errors
        if issue.code not in {"nan_heavy", "no_finite_values", "impossible_value"}
    ]
    if hard_errors:
        raise RegriddingError(
            "Regridded output failed coordinate/structure quality checks: "
            + "; ".join(issue.message for issue in hard_errors)
        )


def _append_processing_level(existing: object, stage: str) -> str:
    if not existing:
        return stage
    text = str(existing)
    if stage in text.split("+"):
        return text
    return f"{text}+{stage}"
