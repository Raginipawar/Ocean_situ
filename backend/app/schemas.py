"""
VARUNA Backend — Pydantic schemas.

Defines all data shapes for the API gateway. These mirror Person 1's
graph_fusion.schemas types so the backend is independently typed and
can validate upstream responses without importing graph_fusion.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ── enums ────────────────────────────────────────────────────────────

class SensorType(str, Enum):
    argo = "argo"
    glider = "glider"
    ctd = "ctd"
    buoy = "buoy"
    mooring = "mooring"
    hf_radar = "hf_radar"
    adcp = "adcp"
    drifter = "drifter"
    xbt = "xbt"


class AlertSeverity(str, Enum):
    info = "info"
    warning = "warning"
    critical = "critical"


TrustLabel = Literal["green", "amber", "red"]


# ── grid / observation points ────────────────────────────────────────

class ModelGridPoint(BaseModel):
    lat: float
    lon: float
    depth_m: float = 0.0
    sst_c: Optional[float] = None
    current_u_ms: Optional[float] = None
    current_v_ms: Optional[float] = None
    wave_height_m: Optional[float] = None


class ObservationPoint(BaseModel):
    sensor_id: str
    sensor_type: SensorType
    lat: float
    lon: float
    depth_m: float = 0.0
    time: datetime
    sst_c: Optional[float] = None
    current_u_ms: Optional[float] = None
    current_v_ms: Optional[float] = None
    wave_height_m: Optional[float] = None


# ── snapshots ────────────────────────────────────────────────────────

class ModelSnapshot(BaseModel):
    region: str
    time: datetime
    resolution_deg: float
    source: str = "mock"
    points: list[ModelGridPoint]


class ObservationSnapshot(BaseModel):
    region: str
    time: datetime
    source: str = "mock"
    points: list[ObservationPoint]


# ── fused output ─────────────────────────────────────────────────────

class FusedPoint(BaseModel):
    lat: float
    lon: float
    depth_m: float = 0.0
    sst_c: Optional[float] = None
    current_u_ms: Optional[float] = None
    current_v_ms: Optional[float] = None
    wave_height_m: Optional[float] = None
    correction_sst_c: Optional[float] = None
    correction_current_u_ms: Optional[float] = None
    correction_current_v_ms: Optional[float] = None
    correction_wave_height_m: Optional[float] = None
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    trust_label: TrustLabel = "green"
    is_sensor_node: bool = False
    support: float = Field(0.0, ge=0.0, le=1.0)


class FusionSummary(BaseModel):
    engine: Literal["gnn", "fallback"]
    n_sensors: int
    n_grid_points: int
    n_graph_edges: int
    mean_confidence: float
    mean_abs_correction_sst_c: Optional[float] = None
    validation_mae_sst_c: Optional[float] = None
    runtime_ms: float


class FusedResponse(BaseModel):
    region: str
    time: datetime
    points: list[FusedPoint]
    summary: FusionSummary


# ── alerts ───────────────────────────────────────────────────────────

class Alert(BaseModel):
    id: str
    region: str = "bay_of_bengal"
    variable: str
    severity: AlertSeverity = AlertSeverity.info
    message: str
    timestamp: datetime
    lat: float
    lon: float
    model_value: float
    observed_value: float
    divergence: float


# ── WebSocket envelope ───────────────────────────────────────────────

class WSMessageType(str, Enum):
    alert = "alert"
    heartbeat = "heartbeat"
    connection_ack = "connection_ack"
    error = "error"


class WSMessage(BaseModel):
    """Envelope for all WebSocket push messages."""
    type: WSMessageType
    payload: dict | list | None = None
    timestamp: datetime


# ── OGC types ────────────────────────────────────────────────────────

class OGCLayer(BaseModel):
    """A single WMS layer."""
    name: str
    title: str
    abstract: str
    unit: str
    colormap: str = "viridis"


# ── CF Conventions metadata ──────────────────────────────────────────

class CFVariableMetadata(BaseModel):
    """CF Conventions metadata for a single variable."""
    standard_name: str
    long_name: str
    units: str
    valid_min: Optional[float] = None
    valid_max: Optional[float] = None


class CFGlobalMetadata(BaseModel):
    """CF Conventions global attributes."""
    Conventions: str = "CF-1.8"
    title: str = "VARUNA Fused Ocean State"
    institution: str = "INCOIS / SIH Team Hudson Hackers"
    source: str = "VARUNA Graph Fusion Engine"
    history: str = ""
    references: str = "https://github.com/varuna-sih"
    comment: str = "Real-time fused ocean state from model + in-situ observations"
