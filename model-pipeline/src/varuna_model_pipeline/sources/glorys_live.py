"""
Live Copernicus Marine GLORYS fetch.

`glorys.py`'s own docstring says: "live Copernicus authentication/download
work is intentionally outside this checkpoint." This module is that missing
piece, added as a proposed contribution (Person 3's track, while gathering
real data for the Nowcast Engine) -- not a modification of glorys.py itself.

Why this belongs here rather than being duplicated per-track: the whole
point of this package is to be the *one* place `/model` data comes from, so
every other track (Graph Fusion, Nowcast, anyone else) consumes the same
real data through the same adapter pattern instead of each independently
re-authenticating and re-fetching from Copernicus. See GlorysIngestor in
glorys.py -- it already accepts "fixture/local NetCDF paths and
xarray-readable URLs"; this module only produces such a path via the
official `copernicusmarine` client, so wiring live data in is:

    from .glorys import GlorysIngestor
    from .glorys_live import fetch_live_glorys_window

    path = fetch_live_glorys_window(settings)
    result = GlorysIngestor(settings).load(path)

...a one-line change at the call site, not a rewrite of any tested parsing
logic.

Requires a one-time `copernicusmarine login` on the machine running this
(caches credentials locally under the user's home directory; nothing is
stored in code or config, and this module never accepts a password
argument on purpose -- credentials management is `copernicusmarine`'s job).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..config import ModelPipelineSettings

logger = logging.getLogger(__name__)

# Same product family used to gather the team's real Bay of Bengal dataset:
# GLORYS reanalysis physics, daily mean, 0.083 degree resolution.
DEFAULT_DATASET_ID = "cmems_mod_glo_phy_my_0.083deg_P1D-m"
DEFAULT_VARIABLES = ["thetao", "so", "uo", "vo"]
DEFAULT_MAX_DEPTH_M = 130.0


def fetch_live_glorys_window(
    settings: ModelPipelineSettings | None = None,
    dataset_id: str = DEFAULT_DATASET_ID,
    variables: list[str] | None = None,
    lookback_days: int = 7,
    max_depth_m: float = DEFAULT_MAX_DEPTH_M,
    output_dir: str | Path = ".",
) -> Path:
    """Pull the most recent `lookback_days` of real GLORYS data for the
    configured Bay of Bengal region into a local NetCDF file, and return its
    path -- ready to hand straight to `GlorysIngestor.load()`.

    Raises ImportError (with install instructions) if `copernicusmarine`
    isn't installed. Raises whatever `copernicusmarine` itself raises if the
    machine hasn't run `copernicusmarine login` yet -- deliberately not
    caught/silenced here, since a swallowed auth failure would otherwise
    look identical to "no data available".
    """
    try:
        import copernicusmarine
    except ImportError as exc:  # pragma: no cover - exercised only when the optional dep is missing
        raise ImportError(
            "copernicusmarine is not installed. Install with "
            "`pip install copernicusmarine`, then run `copernicusmarine login` once."
        ) from exc

    cfg = settings or ModelPipelineSettings()
    variables = variables or DEFAULT_VARIABLES

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=lookback_days)
    output_filename = f"glorys_live_{start:%Y%m%d}_{end:%Y%m%d}.nc"

    logger.info(
        "Fetching live GLORYS window %s -> %s for %s over lon[%.2f, %.2f] lat[%.2f, %.2f]",
        start.date(), end.date(), variables,
        cfg.region.lon_min, cfg.region.lon_max, cfg.region.lat_min, cfg.region.lat_max,
    )
    copernicusmarine.subset(
        dataset_id=dataset_id,
        variables=variables,
        minimum_longitude=cfg.region.lon_min,
        maximum_longitude=cfg.region.lon_max,
        minimum_latitude=cfg.region.lat_min,
        maximum_latitude=cfg.region.lat_max,
        minimum_depth=0.0,
        maximum_depth=max_depth_m,
        start_datetime=start,
        end_datetime=end,
        output_filename=output_filename,
        output_directory=str(output_dir),
        overwrite=True,
        disable_progress_bar=True,
    )

    output_path = Path(output_dir) / output_filename
    logger.info("Live GLORYS window saved to %s", output_path)
    return output_path
