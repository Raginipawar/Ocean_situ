"""
VARUNA In-Situ Pipeline Configuration.

Provides environment variable overrides and sensible defaults for:
- Source selection (demo, real APIs, FTP, NetCDF)
- Bay of Bengal spatial and temporal boundaries
- Quality control filtering thresholds
- Cache and HTTP timeouts
"""
from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .schemas import RegionBounds


class InSituSettings(BaseSettings):
    """Pipeline configuration settings."""
    model_config = SettingsConfigDict(env_prefix="VARUNA_INSITU_", env_file=".env", extra="ignore")

    # Source Selection
    # Available modes: "local_demo", "argovis", "ifremer", "buoy", "wod", "composite"
    active_source: str = "local_demo"
    enabled_adapters: list[str] = ["local_demo", "argovis", "buoy"]

    # Geographic Bounding Box (Bay of Bengal)
    lat_min: float = 5.0
    lat_max: float = 25.0
    lon_min: float = 80.0
    lon_max: float = 100.0
    region_name: str = "bay_of_bengal"

    # Depth Threshold for Surface Snapshot (meters)
    # Observations shallower than this are selected for the /observations 2D surface snapshot
    surface_max_depth_m: float = 10.0

    # Quality Control
    allowed_qc_flags: list[int] = [1, 2]
    filter_sentinels: bool = True
    enforce_physical_limits: bool = True

    # Offline Demo Dataset Path
    demo_data_path: Path | None = Field(
        default=Path(__file__).resolve().parent.parent.parent / "data" / "demo_bay_of_bengal_obs.json",
        description="Path to pre-cached deterministic offline demo dataset",
    )

    # Remote Ingestion Settings
    argovis_api_base: str = "https://argovis-api.colorado.edu"
    argovis_api_key: str | None = None
    http_timeout_s: float = 10.0
    http_max_retries: int = 2

    # Standalone Microservice API Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8002

    @property
    def bounds(self) -> RegionBounds:
        """Construct RegionBounds from configured coordinates."""
        return RegionBounds(
            lat_min=self.lat_min,
            lat_max=self.lat_max,
            lon_min=self.lon_min,
            lon_max=self.lon_max,
            name=self.region_name,
        )


settings = InSituSettings()
