"""
VARUNA In-Situ Pipeline — Data Contracts and Schemas.

Defines:
1. Canonical observation schemas matching Person 1 (graph_fusion) and Person 5 (backend)
   (/observations snapshot contract).
2. Extended multi-variable schemas (salinity, chlorophyll, depth profiles).
3. Geospatial bounding and quality control reporting models.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


class SensorType(str, Enum):
    """Supported marine observation sensor platforms."""
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
    """Geospatial coordinate point with depth."""
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude in degrees north [-90, 90]")
    lon: float = Field(..., ge=-180.0, le=180.0, description="Longitude in degrees east [-180, 180]")
    depth_m: float = Field(0.0, ge=0.0, description="Depth below surface in meters (0 = sea surface)")


class RegionBounds(BaseModel):
    """Geographic bounding box for region filtering."""
    lat_min: float = 5.0
    lat_max: float = 25.0
    lon_min: float = 80.0
    lon_max: float = 100.0
    name: str = "bay_of_bengal"

    def contains(self, lat: float, lon: float) -> bool:
        """Check if coordinates fall within the bounding box."""
        return (self.lat_min <= lat <= self.lat_max) and (self.lon_min <= lon <= self.lon_max)


# ---------------------------------------------------------------------------
# Canonical Contract for /observations (Consumed by Graph Fusion & Backend)
# ---------------------------------------------------------------------------

class ObservationPoint(GeoPoint):
    """
    Standard surface/shallow observation point.
    Matches graph_fusion.schemas.ObservationPoint 1:1.
    """
    sensor_id: str = Field(..., description="Unique platform or cast identifier")
    sensor_type: SensorType = Field(..., description="Type of sensor instrument")
    time: datetime = Field(default_factory=utcnow, description="Observation timestamp in UTC")
    sst_c: float | None = Field(None, description="Sea surface temperature in degrees Celsius")
    current_u_ms: float | None = Field(None, description="Eastward water velocity in m/s")
    current_v_ms: float | None = Field(None, description="Northward water velocity in m/s")
    wave_height_m: float | None = Field(None, description="Significant wave height in meters")

    # Multi-variable extensions (Person 6 Track)
    salinity_psu: float | None = Field(None, description="Practical salinity in PSU / 1e-3")
    chlorophyll_mg_m3: float | None = Field(None, description="Chlorophyll-a in mg/m^3")


class ObservationSnapshot(BaseModel):
    """
    Canonical snapshot payload returned by /observations.
    Matches graph_fusion.schemas.ObservationSnapshot 1:1.
    """
    region: str = Field("bay_of_bengal", description="Region name")
    time: datetime = Field(default_factory=utcnow, description="Snapshot timestamp in UTC")
    source: str = Field("insitu_pipeline", description="Provenance identifier")
    points: list[ObservationPoint] = Field(default_factory=list, description="Array of observed points")


# ---------------------------------------------------------------------------
# Depth-Resolved 3D Profiles (For 3D Inspection & Depth Slicing)
# ---------------------------------------------------------------------------

class ProfileLevel(BaseModel):
    """A single depth measurement in a vertical profile."""
    depth_m: float = Field(..., ge=0.0)
    temperature_c: float | None = None
    salinity_psu: float | None = None
    current_u_ms: float | None = None
    current_v_ms: float | None = None
    chlorophyll_mg_m3: float | None = None
    qc_flag: int = 1


class VerticalProfile(BaseModel):
    """A full vertical cast or dive profile (Argo, CTD, Glider)."""
    sensor_id: str
    sensor_type: SensorType
    lat: float
    lon: float
    time: datetime
    levels: list[ProfileLevel] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Quality Control & Diagnostic Schemas
# ---------------------------------------------------------------------------

class QualityControlReport(BaseModel):
    """Metrics from data sanitation and QC filtering."""
    source: str
    total_raw_records: int = 0
    retained_records: int = 0
    dropped_out_of_bounds: int = 0
    dropped_bad_qc: int = 0
    dropped_sentinels: int = 0
    sanitized_values: int = 0
    execution_time_ms: float = 0.0
