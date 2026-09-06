"""Geographic region extraction for canonical model datasets."""

from __future__ import annotations

import logging

import numpy as np
import xarray as xr

from ..config import RegionBounds
from ..errors import MissingCoordinateError, ModelPipelineError

logger = logging.getLogger(__name__)


class EmptyRegionError(ModelPipelineError):
    """Raised when a requested geographic extraction contains no data."""


def normalize_longitudes(dataset: xr.Dataset, lon_name: str = "lon") -> xr.Dataset:
    """Normalize longitudes to the -180..180 convention and sort by longitude.

    Sources may provide longitudes in 0..360. VARUNA's default Bay of Bengal
    bounds work in either convention, but normalizing once keeps downstream
    extraction predictable for any future region that crosses the dateline or
    uses western longitudes.
    """

    if lon_name not in dataset.coords:
        raise MissingCoordinateError(f"Dataset is missing longitude coordinate {lon_name!r}")

    lon = dataset[lon_name]
    values = np.asarray(lon.values, dtype=float)
    if values.size == 0:
        raise EmptyRegionError("Longitude coordinate is empty")

    if np.nanmax(values) > 180.0:
        normalized = ((values + 180.0) % 360.0) - 180.0
        dataset = dataset.assign_coords({lon_name: normalized})

    return dataset.sortby(lon_name)


def extract_region(
    dataset: xr.Dataset,
    bounds: RegionBounds,
    *,
    lat_name: str = "lat",
    lon_name: str = "lon",
) -> xr.Dataset:
    """Extract a configured lat/lon region from a canonical xarray Dataset.

    The function handles ascending or descending latitude/longitude coordinates
    and validates that the resulting subset contains data. It does not regrid or
    fill missing values.
    """

    _require_coordinate(dataset, lat_name)
    _require_coordinate(dataset, lon_name)

    ds = normalize_longitudes(dataset, lon_name=lon_name)
    lon_min, lon_max = _normalize_bound(bounds.lon_min), _normalize_bound(bounds.lon_max)
    lat_values = np.asarray(ds[lat_name].values, dtype=float)
    lon_values = np.asarray(ds[lon_name].values, dtype=float)

    if lat_values.size == 0:
        raise EmptyRegionError("Latitude coordinate is empty")
    if lon_values.size == 0:
        raise EmptyRegionError("Longitude coordinate is empty")

    lat_subset = _values_in_range(lat_values, bounds.lat_min, bounds.lat_max)
    lon_subset = _values_in_range(lon_values, lon_min, lon_max)

    if lat_subset.size == 0 or lon_subset.size == 0:
        raise EmptyRegionError(
            "Requested region contains no coordinate points: "
            f"region={bounds.name!r}, lat=({bounds.lat_min}, {bounds.lat_max}), "
            f"lon=({bounds.lon_min}, {bounds.lon_max})"
        )

    extracted = ds.sel({lat_name: lat_subset, lon_name: lon_subset})

    if extracted.sizes.get(lat_name, 0) == 0 or extracted.sizes.get(lon_name, 0) == 0:
        raise EmptyRegionError(
            f"Requested region {bounds.name!r} produced an empty dataset after selection"
        )

    extracted.attrs = {
        **extracted.attrs,
        "region": bounds.name,
        "region_lat_min": bounds.lat_min,
        "region_lat_max": bounds.lat_max,
        "region_lon_min": bounds.lon_min,
        "region_lon_max": bounds.lon_max,
        "processing_level": _append_processing_level(
            extracted.attrs.get("processing_level"), "region_extracted"
        ),
    }
    logger.info(
        "Extracted region %s: lat %.3f..%.3f, lon %.3f..%.3f",
        bounds.name,
        bounds.lat_min,
        bounds.lat_max,
        bounds.lon_min,
        bounds.lon_max,
    )
    return extracted


def _require_coordinate(dataset: xr.Dataset, coord_name: str) -> None:
    if coord_name not in dataset.coords:
        raise MissingCoordinateError(f"Dataset is missing coordinate {coord_name!r}")


def _normalize_bound(value: float) -> float:
    if value > 180.0:
        return ((value + 180.0) % 360.0) - 180.0
    return value


def _values_in_range(values: np.ndarray, lower: float, upper: float) -> np.ndarray:
    lo, hi = (lower, upper) if lower <= upper else (upper, lower)
    selected = values[(values >= lo) & (values <= hi)]
    if selected.size == 0:
        return selected
    return np.sort(selected)


def _append_processing_level(existing: object, stage: str) -> str:
    if not existing:
        return stage
    text = str(existing)
    if stage in text.split("+"):
        return text
    return f"{text}+{stage}"

