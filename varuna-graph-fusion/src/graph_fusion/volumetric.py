"""
Real Copernicus-derived volumetric cube (Person 3's export), for the 3D Cube
Explorer's Google-Earth-style free-roam navigation.

Two files, same axes (depth x lat x lon, 0.25deg, 10 real depth levels):
  - varuna_volumetric_cube_latest.nc  (~2.7MB)  one real day
  - varuna_volumetric_cube_full.nc    (~724MB)  270 real consecutive days

Neither is committed to git (see .gitignore's `*.nc`) -- both are expected
to sit at the repo root unless overridden via env var. `xr.open_dataset` is
lazy (confirmed empirically: opens in <0.5s regardless of file size, a
270-day/10-depth/69x81 read for one cell takes ~0.1s, a full single-day
spatial snapshot takes ~3ms), so this module keeps one open Dataset handle
per file rather than loading either fully into memory.

Missing files are a 503 at the endpoint, not a startup crash: the rest of
the app (fused/alerts/profiles/nowcast) doesn't depend on this feature.
"""
from __future__ import annotations

import logging
import pathlib
import threading

from . import config

logger = logging.getLogger("graph_fusion.volumetric")

VARIABLES = ["sst_c", "salinity_psu", "current_u_ms", "current_v_ms", "wave_height_m", "chlorophyll_mg_m3"]

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_DEFAULT_FULL_PATH = _REPO_ROOT / "varuna_volumetric_cube_full.nc"
_DEFAULT_LATEST_PATH = _REPO_ROOT / "varuna_volumetric_cube_latest.nc"

_lock = threading.Lock()
_full_ds = None
_latest_ds = None


class VolumetricUnavailable(RuntimeError):
    pass


def _resolve_path(configured: str | None, default: pathlib.Path) -> pathlib.Path:
    return pathlib.Path(configured) if configured else default


def _open(path: pathlib.Path):
    if not path.exists():
        raise VolumetricUnavailable(
            f"{path} not found. Place the real volumetric cube .nc file at the repo root "
            "(or set VARUNA_VOLUMETRIC_FULL_NC / VARUNA_VOLUMETRIC_LATEST_NC)."
        )
    try:
        import xarray as xr
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise VolumetricUnavailable("xarray isn't installed in this environment.") from exc
    return xr.open_dataset(path)


def _get_full_dataset():
    global _full_ds
    with _lock:
        if _full_ds is None:
            path = _resolve_path(config.SOURCES.volumetric_full_nc_path, _DEFAULT_FULL_PATH)
            _full_ds = _open(path)
            logger.info("Opened full volumetric cube: %s", path)
        return _full_ds


def _get_latest_dataset():
    """Falls back to the full dataset's most recent day if only that file
    is available -- both are equally real, this is just about which file
    happens to be present."""
    global _latest_ds
    with _lock:
        if _latest_ds is not None:
            return _latest_ds
        path = _resolve_path(config.SOURCES.volumetric_latest_nc_path, _DEFAULT_LATEST_PATH)
        if path.exists():
            _latest_ds = _open(path)
            logger.info("Opened latest volumetric cube: %s", path)
            return _latest_ds
    # Outside the lock -- _get_full_dataset takes its own lock.
    return _get_full_dataset()


def _round3(x) -> float:
    return round(float(x), 3)


def get_meta() -> dict:
    ds = _get_latest_dataset()
    has_full = _resolve_path(config.SOURCES.volumetric_full_nc_path, _DEFAULT_FULL_PATH).exists()
    time_values = []
    if has_full:
        full = _get_full_dataset()
        time_values = [str(t)[:10] for t in full["time"].values]
    else:
        time_values = [str(ds["time"].values)[:10]] if "time" in ds.coords else []
    return {
        "region": config.REGION_NAME,
        "lat": [round(float(v), 4) for v in ds["lat"].values],
        "lon": [round(float(v), 4) for v in ds["lon"].values],
        "depth_m": [round(float(v), 2) for v in ds["depth"].values],
        "time": time_values,
        "variables": VARIABLES,
        "source": ds.attrs.get("source", "Copernicus Marine (real)"),
    }


def get_snapshot(day_index: int = -1) -> dict:
    """The full grid, every variable, for one real day (default: the most
    recent). Reads the *latest* single-day file when day_index is -1 and it
    exists (smaller/faster); any other index requires the full file."""
    if day_index == -1:
        ds = _get_latest_dataset()
        snap = ds.isel(time=-1) if "time" in ds.dims else ds
    else:
        ds = _get_full_dataset()
        snap = ds.isel(time=day_index)

    time_label = str(snap["time"].values)[:10] if "time" in snap.coords else "unknown"
    out = {
        "time": time_label,
        "depth_m": [round(float(v), 2) for v in snap["depth"].values],
        "lat": [round(float(v), 4) for v in snap["lat"].values],
        "lon": [round(float(v), 4) for v in snap["lon"].values],
    }
    for var in VARIABLES:
        arr = snap[var].values  # (depth, lat, lon)
        out[var] = [[[_round3(v) for v in row] for row in depth_slice] for depth_slice in arr]
    return out


def get_cell_series(lat: float, lon: float) -> dict:
    """The full real 270-day time series for the grid cell nearest (lat,
    lon), across all 10 real depth levels."""
    ds = _get_full_dataset()
    cell = ds.sel(lat=lat, lon=lon, method="nearest")
    out = {
        "lat": round(float(cell["lat"].values), 4),
        "lon": round(float(cell["lon"].values), 4),
        "depth_m": [round(float(v), 2) for v in cell["depth"].values],
        "time": [str(t)[:10] for t in cell["time"].values],
    }
    for var in VARIABLES:
        arr = cell[var].values  # (time, depth)
        out[var] = [[_round3(v) for v in row] for row in arr]
    return out
