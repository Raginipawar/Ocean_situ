"""
Configuration for the Drift Memory Engine.

Defines Bay of Bengal sub-basins, baseline climatological uncertainties,
divergence threshold tiers, and Titans-inspired memory momentum parameters.
"""
from __future__ import annotations

from typing import NamedTuple
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SubBasinBounds(NamedTuple):
    name: str
    label: str
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float


# Bay of Bengal oceanographic sub-basins
SUB_BASINS: list[SubBasinBounds] = [
    SubBasinBounds(
        name="north_bob",
        label="North Bay of Bengal",
        lat_min=18.0,
        lat_max=22.5,
        lon_min=85.0,
        lon_max=93.0,
    ),
    SubBasinBounds(
        name="central_bob",
        label="Central Bay of Bengal",
        lat_min=13.0,
        lat_max=18.0,
        lon_min=82.0,
        lon_max=93.0,
    ),
    SubBasinBounds(
        name="south_bob",
        label="South Bay of Bengal & Sri Lanka Dome",
        lat_min=5.0,
        lat_max=13.0,
        lon_min=80.0,
        lon_max=88.0,
    ),
    SubBasinBounds(
        name="andaman_sea",
        label="Andaman Sea",
        lat_min=6.0,
        lat_max=15.0,
        lon_min=92.0,
        lon_max=98.5,
    ),
    SubBasinBounds(
        name="coastal_east_india",
        label="East India Coastal Current Zone",
        lat_min=10.0,
        lat_max=20.0,
        lon_min=79.5,
        lon_max=85.0,
    ),
]


def classify_sub_basin(lat: float, lon: float) -> str:
    """Resolve coordinates to the most specific Bay of Bengal sub-basin."""
    # Priority to coastal boundary zone if inside
    if 10.0 <= lat <= 20.0 and 79.5 <= lon <= 85.0:
        return "coastal_east_india"
    for basin in SUB_BASINS:
        if basin.lat_min <= lat <= basin.lat_max and basin.lon_min <= lon <= basin.lon_max:
            return basin.name
    return "bay_of_bengal_general"


class Settings(BaseSettings):
    """Central configuration for Drift Memory Engine. Overridable via VARUNA_DRIFT_ env vars."""

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8002
    region_name: str = "bay_of_bengal"

    # Upstream services for live integration (Day 3)
    graph_fusion_url: str = Field("http://localhost:8001", description="Person 1's Fusion API")
    model_pipeline_url: str = Field("http://localhost:8000/model", description="Person 4's Model API")
    obs_pipeline_url: str = Field("http://localhost:8000/observations", description="Person 6's Obs API")

    # Titans-style Memory Hyperparameters
    # Memory momentum factor alpha: M_t = (1 - alpha) * M_{t-1} + alpha * surprise
    memory_momentum_alpha: float = 0.20
    # Adaptive surprise boost when anomaly exceeds 2.5 sigma
    adaptive_surprise_boost: float = 1.8

    # Baseline Climatological Uncertainties (sigma)
    sigma_sst_c: float = 0.50            # Standard deviation for SST error in BoB
    sigma_current_ms: float = 0.20       # Standard deviation for velocity magnitude
    sigma_wave_height_m: float = 0.35    # Standard deviation for wave height
    sigma_salinity_psu: float = 0.40     # Standard deviation for salinity

    # Physical Divergence Thresholds
    # Sea Surface Temperature (Celsius)
    sst_info_delta: float = 0.60
    sst_warning_delta: float = 1.20
    sst_critical_delta: float = 2.00     # Signals Marine Heatwave (MHW) / severe drift

    # Current Velocity Magnitude (m/s)
    current_info_delta: float = 0.18
    current_warning_delta: float = 0.40
    current_critical_delta: float = 0.75

    # Current Directional Divergence (degrees)
    current_dir_warning_deg: float = 45.0
    current_dir_critical_deg: float = 90.0

    # Wave Height (meters)
    wave_info_delta: float = 0.40
    wave_warning_delta: float = 0.80
    wave_critical_delta: float = 1.50

    # Debounce / Alert Clamping
    # Suppress duplicate alerts for same (sub_basin, variable) within N seconds
    alert_debounce_seconds: float = 300.0

    model_config = SettingsConfigDict(env_prefix="VARUNA_DRIFT_")


settings = Settings()
