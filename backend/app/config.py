"""
VARUNA Backend — centralized configuration.

All settings are driven by environment variables with the VARUNA_ prefix.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central backend configuration. Override via VARUNA_ env vars."""

    # ── upstream services ────────────────────────────────────────────
    # Person 1's Graph Fusion Engine
    graph_fusion_url: str = Field(
        "http://localhost:8001",
        description="Base URL of Person 1's Graph Fusion Engine",
    )

    # Person 4's Model Pipeline (Day 3)
    model_pipeline_url: Optional[str] = Field(
        None,
        description="Base URL of Person 4's model pipeline (None = use graph fusion)",
    )

    # Person 6's Observation Pipeline (Day 3)
    obs_pipeline_url: Optional[str] = Field(
        None,
        description="Base URL of Person 6's observation pipeline (None = use graph fusion)",
    )

    # ── API server ───────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ── WebSocket ────────────────────────────────────────────────────
    ws_heartbeat_interval_s: float = 30.0
    ws_alert_poll_interval_s: float = 5.0
    ws_max_connections: int = 50

    # ── OGC service metadata ─────────────────────────────────────────
    ogc_title: str = "VARUNA Ocean Digital Twin"
    ogc_abstract: str = (
        "Real-time fused ocean state visualization combining INCOIS/HYCOM "
        "model forecasts with Argo/Glider/CTD/Buoy in-situ observations."
    )
    ogc_bbox_lat_min: float = 5.0
    ogc_bbox_lat_max: float = 22.0
    ogc_bbox_lon_min: float = 80.0
    ogc_bbox_lon_max: float = 100.0

    # ── upstream HTTP client ─────────────────────────────────────────
    upstream_timeout_s: float = 10.0
    upstream_max_retries: int = 2
    upstream_cache_ttl_s: float = 10.0

    model_config = {"env_prefix": "VARUNA_", "case_sensitive": False}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
