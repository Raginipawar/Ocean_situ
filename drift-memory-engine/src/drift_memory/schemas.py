"""
VARUNA Drift Memory Engine — Pydantic Data Contracts.

Owns the /alerts schema and drift memory state representations, while also
providing 100% interoperable definitions for upstream /model, /observations,
and /fused payloads (from Person 1, Person 4, and Person 6).
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Enums ────────────────────────────────────────────────────────────

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


# ── Coordinates & Base Points ────────────────────────────────────────

class GeoPoint(BaseModel):
    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)
    depth_m: float = Field(0.0, ge=0.0)


# ── Model Grid Point & Snapshot (Person 4 Contract) ──────────────────

class ModelGridPoint(GeoPoint):
    sst_c: Optional[float] = None
    current_u_ms: Optional[float] = None
    current_v_ms: Optional[float] = None
    wave_height_m: Optional[float] = None
    salinity_psu: Optional[float] = None


class ModelSnapshot(BaseModel):
    region: str = "bay_of_bengal"
    time: datetime = Field(default_factory=_utcnow)
    resolution_deg: float = 1.0
    source: str = "mock"
    points: list[ModelGridPoint]


# ── Observation Point & Snapshot (Person 6 Contract) ────────────────

class ObservationPoint(GeoPoint):
    sensor_id: str
    sensor_type: SensorType = SensorType.buoy
    time: datetime = Field(default_factory=_utcnow)
    sst_c: Optional[float] = None
    current_u_ms: Optional[float] = None
    current_v_ms: Optional[float] = None
    wave_height_m: Optional[float] = None
    salinity_psu: Optional[float] = None


class ObservationSnapshot(BaseModel):
    region: str = "bay_of_bengal"
    time: datetime = Field(default_factory=_utcnow)
    source: str = "mock"
    points: list[ObservationPoint]


# ── Fused Output (Person 1 Contract) ─────────────────────────────────

class FusedPoint(GeoPoint):
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
    engine: Literal["gnn", "fallback"] = "gnn"
    n_sensors: int = 0
    n_grid_points: int = 0
    n_graph_edges: int = 0
    mean_confidence: float = 1.0
    mean_abs_correction_sst_c: Optional[float] = None
    validation_mae_sst_c: Optional[float] = None
    runtime_ms: float = 0.0


class FusedResponse(BaseModel):
    region: str = "bay_of_bengal"
    time: datetime = Field(default_factory=_utcnow)
    points: list[FusedPoint]
    summary: FusionSummary


# ── Alerts (Person 2 Deliverable — Exact Match to Backend) ────────────

class Alert(BaseModel):
    """
    Live alert payload.
    Emitted by Drift Memory Engine, consumed by Person 5's REST/WebSocket
    and rendered in CesiumJS alert panel.
    """
    id: str
    region: str = "bay_of_bengal"
    variable: str                                # "sst", "currents", "wave_height", "salinity"
    severity: AlertSeverity = AlertSeverity.info
    message: str
    timestamp: datetime = Field(default_factory=_utcnow)
    lat: float
    lon: float
    model_value: float
    observed_value: float
    divergence: float


# ── Memory Diagnostics & Inspection ───────────────────────────────────

class SubBasinMemoryState(BaseModel):
    """
    Rolling memory state for a single sub-basin and variable,
    implementing test-time surprise accumulation (Titans-style).
    """
    sub_basin: str
    variable: str
    rolling_drift: float                         # Rolling expectation of divergence
    rolling_surprise: float                      # Instantaneous normalized surprise
    observation_count: int
    last_updated: datetime
    active_severity: AlertSeverity = AlertSeverity.info
    is_anomalous: bool = False


class MemorySnapshotResponse(BaseModel):
    """Diagnostic state of the entire ocean memory grid."""
    region: str = "bay_of_bengal"
    timestamp: datetime = Field(default_factory=_utcnow)
    memory_states: list[SubBasinMemoryState]
    total_active_alerts: int
    systematic_drift_detected: bool
