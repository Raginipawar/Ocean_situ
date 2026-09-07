"""
Real Copernicus Marine ocean data loader -- the actual training data source
for the 3D Nowcast Engine.

Loads the real files gathered from Copernicus Marine (GLORYS reanalysis
daily Temperature/Salinity/U/V, Waves Reanalysis 3-hourly wave height,
Biogeochemistry Hindcast monthly chlorophyll), regrids every variable onto
one shared spatial grid and depth-level set, and produces a single real,
depth-resolved, multi-variable daily time series over the 90-day window
where the fine-grained sources overlap (Jan 1 - Mar 31 2023). No synthetic
data is used when these files are present -- synthetic_ocean.py remains a
standalone fallback only for running this package without them.

Cadence handling -- disclosed, not hidden, since sources are genuinely
sampled at different real rates:
  - Temperature/Salinity/U/V: real daily values, used as-is.
  - Wave height: real 3-hourly values, averaged to a real daily mean.
  - Chlorophyll: only available monthly (its native product resolution);
    each real monthly value is held constant (forward-filled) across the
    days within that month, rather than fabricated at daily resolution.
    Chlorophyll is slow-varying physically, so this is a standard,
    defensible simplification -- not invented data.

Regridding note: unlike varuna_model_pipeline's `regrid_to_target` (found,
while building this track, to intermittently return non-deterministic
garbage via xarray's combined multi-dim `.interp()` -- see real_data.py's
docstring), this module interpolates lat/lon only, one variable at a time,
and selects depth levels by integer position rather than interpolating
across them -- deliberately avoiding the same code path that was buggy.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import xarray as xr

logger = logging.getLogger(__name__)

# Shared target grid. 0.25 degree -- finer than the original 1.0 degree
# config grid and finer than the first CPU-only pass (0.5 degree), sized for
# GPU-accelerated training (RTX 3050 6GB) rather than CPU-only.
TARGET_LAT = np.arange(5.0, 22.0 + 1e-9, 0.25)      # 69 points
TARGET_LON = np.arange(80.0, 100.0 + 1e-9, 0.25)    # 81 points

# Representative depth levels chosen by position from the 23-level native
# GLORYS grid: every second level from surface to ~65m --
# [0.49, 2.65, 5.08, 7.93, 11.4, 15.8, 21.6, 29.4, 40.3, 55.8] meters.
TARGET_DEPTH_IDX = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18]

VARIABLES = [
    "sst_c",
    "salinity_psu",
    "current_u_ms",
    "current_v_ms",
    "wave_height_m",
    "chlorophyll_mg_m3",
]


def _regrid(da: xr.DataArray, has_depth: bool) -> xr.DataArray:
    """Interpolate one variable's DataArray onto the shared target lat/lon
    grid. If it has a depth dimension, select the shared representative
    levels by integer position first (never by cross-source depth
    interpolation -- see module docstring)."""
    da = da.rename({"latitude": "lat", "longitude": "lon"})
    if has_depth:
        da = da.isel(depth=TARGET_DEPTH_IDX)
    return da.interp(lat=TARGET_LAT, lon=TARGET_LON, method="linear")


def load_real_training_volume(
    phy_daily_path: str | Path | list[str | Path],
    wave_path: str | Path,
    chlorophyll_path: str | Path,
) -> dict[str, np.ndarray]:
    """Returns {variable_name: array of shape (T, D, H, W)} over the real
    daily temperature/salinity/current window(s) given. `phy_daily_path` may
    be a single file or a list of files (e.g. two separate real download
    windows fetched at different times) -- concatenated chronologically
    along time before regridding, so training sees one continuous real
    timeline rather than two independent short ones."""
    if isinstance(phy_daily_path, (list, tuple)):
        phy = xr.concat([xr.open_dataset(p) for p in phy_daily_path], dim="time").sortby("time")
    else:
        phy = xr.open_dataset(phy_daily_path)
    wave = xr.open_dataset(wave_path)
    chl = xr.open_dataset(chlorophyll_path)

    time = phy.time.values  # real daily timestamps, chronologically sorted

    sst = _regrid(phy["thetao"], has_depth=True)
    sal = _regrid(phy["so"], has_depth=True)
    u = _regrid(phy["uo"], has_depth=True)
    v = _regrid(phy["vo"], has_depth=True)

    wave_daily = wave["VHM0"].resample(time="1D").mean()
    wave_daily = wave_daily.reindex(time=time, method="nearest")
    wave_surface = _regrid(wave_daily, has_depth=False)
    # Wave height is a surface property; broadcast it across the shared
    # depth levels so every channel has the same (T, D, H, W) tensor shape
    # the ConvLSTM expects -- a deliberate simplification, not a claim that
    # wave height varies with depth.
    wave_volume = wave_surface.expand_dims(depth=len(TARGET_DEPTH_IDX), axis=1)

    chl_regridded = _regrid(chl["chl"], has_depth=True)
    chl_daily = chl_regridded.reindex(time=time, method="ffill")

    out = {
        "sst_c": sst.values,
        "salinity_psu": sal.values,
        "current_u_ms": u.values,
        "current_v_ms": v.values,
        "wave_height_m": wave_volume.values,
        "chlorophyll_mg_m3": chl_daily.values,
    }

    for name, arr in out.items():
        n_nan = np.isnan(arr).sum()
        logger.info("%s: shape=%s, nan_fraction=%.4f, range=(%.3f, %.3f)",
                     name, arr.shape, n_nan / arr.size, np.nanmin(arr), np.nanmax(arr))

    return out
