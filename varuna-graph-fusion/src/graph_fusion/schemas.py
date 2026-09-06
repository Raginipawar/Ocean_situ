"""
Pydantic data contracts for the four VARUNA API endpoints described in the
approach document: /model, /observations, /fused, /alerts.

This module owns /model, /observations and /fused (the ones the Graph Fusion
Engine produces or consumes). /alerts belongs to Person 2's Drift Memory
Engine and is intentionally not modelled here.

NOTE: this is a *proposed* contract so Person 1's track is unblocked from
Day 1. Per the team's Round-2 work distribution doc, the real shape should be
confirmed in the Day-1 group sync with Person 4 (/model owner), Person 5
(API layer owner) and Person 6 (/observations owner). If the agreed contract
differs, update this file only -- every other module in this package talks to
the system exclusively through these types.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SensorType(str, Enum):
    ARGO = "argo"
    GLIDER = "glider"
    CTD = "ctd"
    BUOY = "buoy"
    # Named in the approach doc's own vocabulary ("moorings, HF-radar,
    # ADCP-ready", "moored buoys, XBT casts and drifters") -- added ahead of
    # time so a real /observations feed using one of these doesn't fail
    # Pydantic's enum validation and drop otherwise-good readings.
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
# /model  (Version A -- the simulated ocean; owned by Person 4)
# ---------------------------------------------------------------------------

class ModelGridPoint(GeoPoint):
    sst_c: float | None = None
    current_u_ms: float | None = None
    current_v_ms: float | None = None
    wave_height_m: float | None = None


class ModelSnapshot(BaseModel):
    region: str
    time: datetime = Field(default_factory=_utcnow)
    resolution_deg: float
    source: str = Field("mock", description="e.g. 'INCOIS-LAS', 'copernicus-glorys', 'mock'")
    points: list[ModelGridPoint]


# ---------------------------------------------------------------------------
# /observations  (Version B -- the real ocean; owned by Person 6)
# ---------------------------------------------------------------------------

class ObservationPoint(GeoPoint):
    sensor_id: str
    sensor_type: SensorType
    time: datetime = Field(default_factory=_utcnow)
    sst_c: float | None = None
    current_u_ms: float | None = None
    current_v_ms: float | None = None
    wave_height_m: float | None = None


class ObservationSnapshot(BaseModel):
    region: str
    time: datetime = Field(default_factory=_utcnow)
    source: str = Field("mock", description="e.g. 'argovis', 'coriolis-gdac', 'mock'")
    points: list[ObservationPoint]


# ---------------------------------------------------------------------------
# /fused  (the Graph Fusion Engine's output -- this track's deliverable)
# ---------------------------------------------------------------------------

TrustLabel = Literal["green", "amber", "red"]


class FusedPoint(GeoPoint):
    sst_c: float | None = None
    current_u_ms: float | None = None
    current_v_ms: float | None = None
    wave_height_m: float | None = None

    correction_sst_c: float | None = None
    correction_current_u_ms: float | None = None
    correction_current_v_ms: float | None = None
    correction_wave_height_m: float | None = None

    confidence: float = Field(..., ge=0.0, le=1.0)
    trust_label: TrustLabel
    is_sensor_node: bool = Field(
        False, description="True if this point sits exactly at a real sensor location"
    )
    support: float = Field(
        0.0, ge=0.0, le=1.0, description="How much nearby real-sensor evidence backs this point"
    )


class FusionSummary(BaseModel):
    engine: Literal["gnn", "fallback"]
    n_sensors: int
    n_grid_points: int
    n_graph_edges: int
    mean_confidence: float
    mean_abs_correction_sst_c: float | None = None
    validation_mae_sst_c: float | None = Field(
        None,
        description=(
            "Leave-some-sensors-out cross-validation MAE for the GNN engine "
            "(null when the fallback engine ran, since it isn't a trained model)."
        ),
    )
    runtime_ms: float


class FusedResponse(BaseModel):
    region: str
    time: datetime = Field(default_factory=_utcnow)
    points: list[FusedPoint]
    summary: FusionSummary
