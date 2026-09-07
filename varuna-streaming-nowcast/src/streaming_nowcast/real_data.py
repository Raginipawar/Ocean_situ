"""
Bridge to Person 4's real Ocean Model Data Pipeline (`varuna_model_pipeline`),
so this track's mock stream and Nowcast Engine are anchored in genuine
Bay-of-Bengal spatial structure instead of an arbitrary invented formula.

Only the pre-regrid stages are used (`LocalDemoSource` -> `extract_region` ->
`normalize_model_dataset`). `regrid_to_target`'s `.interp(method="linear")`
call was found, while building this track, to intermittently return
non-deterministic, physically impossible values (SST as high as ~1e280 C) on
identical deterministic input across repeated runs -- a real bug in that
module (reported back to the team, not something this track silently works
around). The native-resolution grid read here is exactly two-fold finer than,
and grid-aligned with, the 1.0 degree target grid this track shares with
Person 1 (see config.GRID_RESOLUTION_DEG) -- a plain stride-2 subsample
reproduces the intended target grid without going through the broken
interpolation path.

If `varuna_model_pipeline` isn't importable at all (e.g. this package copied
out of the monorepo and run standalone), falls back to a small synthetic
analytic field with a one-time warning -- same graceful-degradation
philosophy as varuna-graph-fusion's fallback engine.
"""
from __future__ import annotations

import logging
import sys
import warnings
from functools import lru_cache
from pathlib import Path

import numpy as np

from . import config

logger = logging.getLogger(__name__)

# variable name this track/graph_fusion use  ->  canonical name in the model pipeline
_VARIABLE_MAP = {
    "sst_c": "sst",
    "current_u_ms": "u_current",
    "current_v_ms": "v_current",
    "wave_height_m": "wave_height",
    "salinity_psu": "salinity",
    "chlorophyll_mg_m3": "chlorophyll",
}


def _synthetic_fallback_field(lat: np.ndarray, lon: np.ndarray, variable: str) -> np.ndarray:
    """Only used if Person 4's real pipeline package can't be found at all --
    same spirit as varuna-graph-fusion/src/graph_fusion/mock_data.py."""
    fields = {
        "sst_c": 29.5 - 0.33 * (lat - config.LAT_MIN) + 0.4 * np.sin(np.radians(lon) * 5.0),
        "current_u_ms": 0.1 * np.sin(np.radians(lat) * 8.0),
        "current_v_ms": 0.05 * np.cos(np.radians(lon) * 5.0),
        "wave_height_m": 1.2 + 0.2 * np.sin(np.radians(lon - config.LON_MIN) * 12.0),
        "salinity_psu": 34.0 + 0.2 * np.cos(np.radians(lat) * 4.0),
        "chlorophyll_mg_m3": 0.2 + 0.05 * np.exp(-((lat - 17.0) ** 2 + (lon - 91.0) ** 2) / 20.0),
    }
    return fields[variable]


def _add_sibling_pipeline_to_path() -> None:
    """This package lives at <repo>/varuna-streaming-nowcast/src/streaming_nowcast/.
    Person 4's package lives at <repo>/model-pipeline/src/. Add it to
    sys.path so the real pipeline is picked up automatically inside a full
    monorepo checkout, without requiring a separate `pip install -e` step."""
    repo_root = Path(__file__).resolve().parents[3]
    sibling_src = repo_root / "model-pipeline" / "src"
    if sibling_src.is_dir() and str(sibling_src) not in sys.path:
        sys.path.insert(0, str(sibling_src))


@lru_cache(maxsize=1)
def _load_real_snapshot():
    """Load Person 4's real, deterministic Bay-of-Bengal grid at native
    (pre-regrid) resolution. Cached: the source is deterministic, and
    reloading a fresh xarray Dataset on every sensor reading would be wasted
    work in a streaming context.

    Returns (lat_1d, lon_1d, {api_variable_name: 2D array}), or None if the
    real pipeline isn't importable at all.
    """
    _add_sibling_pipeline_to_path()
    try:
        from varuna_model_pipeline.config import ModelPipelineSettings
        from varuna_model_pipeline.pipeline import load_model_data
        from varuna_model_pipeline.processing.normalize import normalize_model_dataset
        from varuna_model_pipeline.processing.region import extract_region
    except ImportError:
        warnings.warn(
            "varuna_model_pipeline not importable -- falling back to a synthetic "
            "analytic field. Run from inside the full VARUNA monorepo checkout "
            "to use Person 4's real local-demo data instead.",
            RuntimeWarning,
            stacklevel=2,
        )
        return None

    cfg = ModelPipelineSettings()
    loaded = load_model_data(use_local_demo=True, settings=cfg)
    region = extract_region(loaded.dataset, cfg.region)
    normalized, _quality = normalize_model_dataset(region, required_variables=cfg.required_variables)

    lat = np.asarray(normalized["lat"].values, dtype=float)
    lon = np.asarray(normalized["lon"].values, dtype=float)

    fields: dict[str, np.ndarray] = {}
    for api_name, source_name in _VARIABLE_MAP.items():
        if source_name not in normalized.data_vars:
            continue
        arr = normalized[source_name]
        if "depth" in arr.dims:
            arr = arr.isel(depth=0)  # surface only
        if "time" in arr.dims:
            arr = arr.isel(time=0)  # single-snapshot demo source
        fields[api_name] = np.asarray(arr.values, dtype=float)

    logger.info(
        "Loaded Person 4's real local-demo grid: %d x %d, variables=%s",
        lat.size, lon.size, list(fields),
    )
    return lat, lon, fields


def target_grid_axes() -> tuple[np.ndarray, np.ndarray]:
    """The 1.0 degree target grid axes this whole track is scoped to --
    identical to varuna-graph-fusion/src/graph_fusion/config.py."""
    lat = np.arange(config.LAT_MIN, config.LAT_MAX + 1e-9, config.GRID_RESOLUTION_DEG)
    lon = np.arange(config.LON_MIN, config.LON_MAX + 1e-9, config.GRID_RESOLUTION_DEG)
    return lat, lon


def real_base_grid(variable: str = "sst_c") -> np.ndarray:
    """The real (or, failing that, synthetic-fallback) base field for
    `variable`, already on the shared 1.0 degree target grid -- shape
    (config.NOWCAST.grid_height, config.NOWCAST.grid_width)."""
    target_lat, target_lon = target_grid_axes()
    real = _load_real_snapshot()

    if real is None:
        lon_grid, lat_grid = np.meshgrid(target_lon, target_lat)
        return _synthetic_fallback_field(lat_grid, lon_grid, variable)

    lat, lon, fields = real
    if variable not in fields:
        lon_grid, lat_grid = np.meshgrid(target_lon, target_lat)
        return _synthetic_fallback_field(lat_grid, lon_grid, variable)

    # Native grid is exactly two-fold finer than, and grid-aligned with, the
    # target grid (see module docstring) -- a stride-2 subsample reproduces
    # the target grid exactly, bypassing regrid_to_target's broken .interp().
    stride = round(config.GRID_RESOLUTION_DEG / float(lat[1] - lat[0]))
    grid = fields[variable][::stride, ::stride]

    if grid.shape != (target_lat.size, target_lon.size):
        raise ValueError(
            f"real base grid shape {grid.shape} does not match the expected "
            f"target grid {(target_lat.size, target_lon.size)} -- Person 4's "
            f"native resolution or bounding box may have changed; update the "
            f"stride logic in real_data.py"
        )
    return grid


def sample_point(lat_query: float, lon_query: float, variable: str = "sst_c") -> float:
    """Nearest-neighbour lookup of `variable` at one (lat, lon) from the real
    (or fallback) base field -- anchors a single mock sensor reading in
    genuine spatial structure instead of an arbitrary formula."""
    target_lat, target_lon = target_grid_axes()
    grid = real_base_grid(variable)
    i = int(np.argmin(np.abs(target_lat - lat_query)))
    j = int(np.argmin(np.abs(target_lon - lon_query)))
    return float(grid[i, j])
