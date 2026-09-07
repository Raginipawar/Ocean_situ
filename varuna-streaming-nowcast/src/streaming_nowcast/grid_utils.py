"""
Grid <-> point-list conversions.

/model, /observations, /fused, /alerts, and this track's own NowcastSnapshot
all talk in flat point lists. The ConvLSTM Nowcast Engine needs a regular 2D
grid -- that's the whole point of ConvLSTM over a plain LSTM (Section 10 of
the work brief: it replaces fully-connected gates with convolutions so it can
process a spatial grid). This module is the one place that translates
between the two shapes, so nothing else has to know both representations.
"""
from __future__ import annotations

import numpy as np

from . import real_data
from .schemas import ModelSnapshot, NowcastGridPoint, NowcastSnapshot


def points_to_grid(snapshot: ModelSnapshot, variable: str) -> np.ndarray:
    """Bin a ModelSnapshot's points onto the shared 1.0 degree target grid
    (config.LAT_MIN..LAT_MAX / LON_MIN..LON_MAX, config.GRID_RESOLUTION_DEG --
    identical to varuna-graph-fusion's grid). Each point is placed at its
    nearest grid cell; cells with no matching point are NaN, not zero, so a
    sparse snapshot doesn't silently look like a real zero reading."""
    target_lat, target_lon = real_data.target_grid_axes()
    grid = np.full((target_lat.size, target_lon.size), np.nan, dtype=np.float32)
    for point in snapshot.points:
        value = getattr(point, variable, None)
        if value is None:
            continue
        i = int(np.argmin(np.abs(target_lat - point.lat)))
        j = int(np.argmin(np.abs(target_lon - point.lon)))
        grid[i, j] = value
    return grid


def grid_to_nowcast_snapshot(
    grid: np.ndarray,
    region: str,
    resolution_deg: float,
    lead_time_s: float,
    status: str = "working",
) -> NowcastSnapshot:
    """The Section 12 hand-off shape: turn a predicted grid back into a point
    list for Person 2 (Drift Memory) or the frontend to consume, if the team
    decides the Nowcast Engine is worth wiring in as a second comparison
    signal -- this is optional per the work brief, not a committed contract."""
    target_lat, target_lon = real_data.target_grid_axes()
    if grid.shape != (target_lat.size, target_lon.size):
        raise ValueError(f"grid shape {grid.shape} does not match the target grid {(target_lat.size, target_lon.size)}")

    points = [
        NowcastGridPoint(lat=float(target_lat[i]), lon=float(target_lon[j]), sst_c=float(grid[i, j]))
        for i in range(grid.shape[0])
        for j in range(grid.shape[1])
    ]
    return NowcastSnapshot(
        region=region,
        resolution_deg=resolution_deg,
        lead_time_s=lead_time_s,
        points=points,
        status=status,
    )
