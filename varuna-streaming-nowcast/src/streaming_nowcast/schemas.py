"""
Pydantic data contracts for Person 3's track (Streaming Backbone + Nowcast
Engine) and the two upstream endpoints it reads from.

This module owns NOTHING that another track owns -- /model and /observations
are mirrored here (read-only, same pattern as
varuna-graph-fusion/src/graph_fusion/schemas.py) purely so this package is
independently typed and runnable standalone, without importing another
track's package. If the real Day-1-locked contract differs, update this file
only -- every other module here talks to the system exclusively through
these types.

New types this module *does* own: StreamingState (introspection into the
backbone's live state) and NowcastSnapshot/NowcastGridPoint (the optional
hand-off contract to Person 2's Drift Memory and the frontend, per Section 12
of the work brief -- "possible Nowcast prediction as a second comparison
signal, only if the team agrees it's worth wiring in").
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SensorType(str, Enum):
    ARGO = "argo"
    GLIDER = "glider"
    CTD = "ctd"
    BUOY = "buoy"
    MOORING = "mooring"
    HF_RADAR = "hf_radar"
    ADCP = "adcp"
    DRIFTER = "drifter"
    XBT = "xbt"


class GeoPoint(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    depth_m: float = Field(0.0, ge=0, description="0 = surface")


# ---------------------------------------------------------------------------
# /model  (mirrored, read-only -- owned by Person 4)
# ---------------------------------------------------------------------------

class ModelGridPoint(GeoPoint):
    sst_c: float | None = None
    current_u_ms: float | None = None
    current_v_ms: float | None = None
    wave_height_m: float | None = None
    salinity_psu: float | None = None
    chlorophyll_mg_m3: float | None = None


class ModelSnapshot(BaseModel):
    region: str
    time: datetime = Field(default_factory=_utcnow)
    resolution_deg: float
    source: str = Field("mock", description="e.g. 'INCOIS-LAS', 'copernicus-glorys', 'mock'")
    points: list[ModelGridPoint]


# ---------------------------------------------------------------------------
# /observations  (mirrored, read-only -- owned by Person 6)
# ---------------------------------------------------------------------------

class ObservationPoint(GeoPoint):
    sensor_id: str
    sensor_type: SensorType
    time: datetime = Field(default_factory=_utcnow)
    sst_c: float | None = None
    current_u_ms: float | None = None
    current_v_ms: float | None = None
    wave_height_m: float | None = None
    salinity_psu: float | None = None
    chlorophyll_mg_m3: float | None = None


class ObservationSnapshot(BaseModel):
    region: str
    time: datetime = Field(default_factory=_utcnow)
    source: str = Field("mock", description="e.g. 'argovis', 'coriolis-gdac', 'mock'")
    points: list[ObservationPoint]


# ---------------------------------------------------------------------------
# Streaming Backbone -- live state introspection (this track's, Section 9)
# ---------------------------------------------------------------------------

class StreamingState(BaseModel):
    """A snapshot of the backbone's internal state at one point in time.

    Not a REST contract (Person 3 does not own endpoints -- Person 5 does,
    per Section 4 of the work brief); this is the shape used for demo
    printing/logging and for handing state to whichever module needs it.
    """
    step: int
    timestamp: datetime = Field(default_factory=_utcnow)
    hidden_state: list[float]
    cell_state: list[float]
    last_input: list[float] | None = Field(
        None, description="None when this step was a gap (missing reading)"
    )
    was_gap: bool = False


# ---------------------------------------------------------------------------
# Nowcast Engine -- optional short-range prediction (this track's, Section 10)
# ---------------------------------------------------------------------------

class NowcastGridPoint(GeoPoint):
    sst_c: float | None = None


class NowcastSnapshot(BaseModel):
    region: str
    time: datetime = Field(default_factory=_utcnow)
    lead_time_s: float = Field(..., description="How far into the future this prediction is for")
    resolution_deg: float
    source: str = Field("nowcast-convlstm")
    points: list[NowcastGridPoint]
    status: str = Field(
        "working",
        description="One of: working, partial, future_scope -- per Section 7 Task 3.C",
    )
