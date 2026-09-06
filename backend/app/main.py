"""
VARUNA Backend — FastAPI application entry point.

Wires together:
  - REST API router  (/api/model, /observations, /fused, /alerts, /health, /cf-metadata)
  - WebSocket router (/ws/alerts)
  - OGC Standards router (/ogc/wms, /ogc/wcs)
  - UpstreamClient lifecycle (start on startup, stop on shutdown)
  - AlertManager polling background task

Run with:
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

Or via the project script:
    varuna-backend
"""
from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers.ogc import router as ogc_router
from .routers.rest import router as rest_router
from .routers.websocket import alert_manager, router as ws_router
from .services.upstream import UpstreamClient

# ── logging setup ────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("varuna.main")


# ── lifespan ─────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.

    On startup:
      1. Create and start the shared UpstreamClient (connection pool).
      2. Attach it to app.state so all routers can access it via
         ``request.app.state.upstream``.
      3. Launch the AlertManager background polling task.

    On shutdown:
      1. Stop the AlertManager (cancels polling + closes WS connections).
      2. Close the UpstreamClient (drains connection pool).
    """
    settings = get_settings()

    logger.info("[VARUNA] Backend starting up ...")
    logger.info("  Upstream graph fusion -> %s", settings.graph_fusion_url)
    logger.info("  WS poll interval      -> %.1fs", settings.ws_alert_poll_interval_s)
    logger.info("  WS heartbeat interval -> %.1fs", settings.ws_heartbeat_interval_s)

    # Start upstream HTTP client
    upstream = UpstreamClient(settings)
    await upstream.start()
    app.state.upstream = upstream

    # Launch WebSocket alert polling
    alert_manager.start(app)

    logger.info("[VARUNA] Backend ready")

    yield  # <- server is running

    # Graceful shutdown
    logger.info("[VARUNA] Backend shutting down ...")
    await alert_manager.stop()
    await upstream.stop()
    logger.info("[VARUNA] Backend stopped")


# ── app factory ──────────────────────────────────────────────────────

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="VARUNA Backend API",
        description=(
            "Central API gateway for the VARUNA Ocean Digital Twin. "
            "Provides REST endpoints, real-time WebSocket alerts, and "
            "OGC WMS/WCS compliance for the SIH 2026 prototype."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── CORS ─────────────────────────────────────────────────────────
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.debug("CORS origins: %s", origins)

    # ── routers ──────────────────────────────────────────────────────
    app.include_router(rest_router)   # /api/*
    app.include_router(ws_router)     # /ws/alerts
    app.include_router(ogc_router)    # /ogc/wms, /ogc/wcs

    # ── root redirect to docs ─────────────────────────────────────────
    @app.get("/", include_in_schema=False)
    async def root() -> dict:
        return {
            "service": "varuna-backend",
            "version": "0.1.0",
            "docs": "/docs",
            "health": "/api/health",
            "endpoints": {
                "model": "/api/model",
                "observations": "/api/observations",
                "fused": "/api/fused",
                "alerts": "/api/alerts",
                "websocket_alerts": "/ws/alerts",
                "ogc_wms": "/ogc/wms?SERVICE=WMS&REQUEST=GetCapabilities",
                "ogc_wcs": "/ogc/wcs?SERVICE=WCS&REQUEST=GetCapabilities",
                "cf_metadata": "/api/cf-metadata",
            },
        }

    return app


# Module-level app instance (for uvicorn "app.main:app")
app = create_app()


# ── CLI entry point ──────────────────────────────────────────────────

def run() -> None:
    """Entry point for the ``varuna-backend`` CLI command."""
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    run()
