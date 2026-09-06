"""
VARUNA Model Pipeline — API Integration Contract

Converts the canonical internal xarray.Dataset into the exact Pydantic schema
expected by the backend's `/model` endpoint and the Graph Fusion Engine.
"""
from datetime import datetime, timezone
import math
from typing import Optional

from pydantic import BaseModel, Field
import xarray as xr
import pandas as pd
import numpy as np


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GeoPoint(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    depth_m: float = Field(0.0, ge=0, description="0 = surface")


class ModelGridPoint(GeoPoint):
    sst_c: Optional[float] = None
    current_u_ms: Optional[float] = None
    current_v_ms: Optional[float] = None
    wave_height_m: Optional[float] = None


class ModelSnapshot(BaseModel):
    region: str
    time: datetime = Field(default_factory=_utcnow)
    resolution_deg: float
    source: str = Field("mock", description="e.g. 'INCOIS-LAS', 'copernicus-glorys', 'mock'")
    points: list[ModelGridPoint]


def _safe_float(val) -> Optional[float]:
    """Convert numpy float to Python float, mapping NaN to None."""
    if val is None or pd.isna(val):
        return None
    f = float(val)
    if math.isnan(f):
        return None
    return f


def to_model_snapshot(ds: xr.Dataset) -> ModelSnapshot:
    """
    Serialize the canonical model xarray.Dataset into the ModelSnapshot payload
    required by the backend and graph fusion engine.

    Args:
        ds: The canonical xarray.Dataset (from process_model_data).

    Returns:
        A validated ModelSnapshot object.
    """
    # Extract dataset attributes
    region = ds.attrs.get("region", "unknown")
    source = ds.attrs.get("source", "unknown")
    resolution = float(ds.attrs.get("target_resolution_deg", 0.0))

    # Extract time (assume single timestep for snapshot)
    if "time" in ds.coords and ds.coords["time"].size > 0:
        time_val = np.ravel(ds.coords["time"].values)[0]
        # Convert numpy datetime64 to python datetime, set UTC
        ts = pd.Timestamp(time_val)
        snapshot_time = ts.to_pydatetime().replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts.to_pydatetime()
    else:
        snapshot_time = _utcnow()

    # If dataset has a time dimension, squeeze it out for spatial iteration
    if "time" in ds.dims:
        # Take the first timestep for the snapshot
        ds = ds.isel(time=0)

    # Convert to dataframe for easy iteration over grid points
    df = ds.to_dataframe().reset_index()

    points = []
    for _, row in df.iterrows():
        point = ModelGridPoint(
            lat=row["lat"],
            lon=row["lon"],
            depth_m=row.get("depth", 0.0),
            sst_c=_safe_float(row.get("sst")),
            current_u_ms=_safe_float(row.get("u_current")),
            current_v_ms=_safe_float(row.get("v_current")),
            wave_height_m=_safe_float(row.get("wave_height")),
        )
        points.append(point)

    return ModelSnapshot(
        region=region,
        time=snapshot_time,
        resolution_deg=resolution,
        source=source,
        points=points,
    )
