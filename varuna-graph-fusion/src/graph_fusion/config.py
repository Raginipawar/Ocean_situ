"""
Central configuration for the VARUNA Graph Fusion Engine (Person 1 / Intelligence Core #1).

Scope-locked for the SIH26067 demo per the team's approach document:
  Region: Bay of Bengal
  Variables: Sea Surface Temperature (SST), Currents (u/v), Wave Height

Every tunable knob the engine uses lives here so the whole pipeline can be
re-scoped (new region, new variable set, new graph density) without touching
engine code.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Region + variable scope (matches "Scope lock for the demo" in the approach doc)
# ---------------------------------------------------------------------------

REGION_NAME = "bay_of_bengal"

# Bounding box roughly covering the Bay of Bengal.
LAT_MIN = 5.0
LAT_MAX = 22.0
LON_MIN = 80.0
LON_MAX = 100.0

# Coarse demo grid resolution in degrees. The real /model pipeline (Person 4)
# will likely serve a finer native grid; the fusion engine does not assume any
# particular resolution because it operates on a graph, not a fixed grid shape.
GRID_RESOLUTION_DEG = 1.0

# Primary variable list. SST is first and is the "never cut" variable per the
# risk/fallback plan: if currents/wave height aren't stable in time, the whole
# pipeline can run with VARIABLES = ["sst_c"] and nothing downstream breaks.
VARIABLES = ["sst_c", "current_u_ms", "current_v_ms", "wave_height_m"]
SST_ONLY_VARIABLES = ["sst_c"]

# Physically-motivated normalisation ranges used only for feature scaling
# (NOT clipped in the output) so the GNN sees inputs roughly in [-1, 1].
VARIABLE_RANGES = {
    "sst_c": (20.0, 32.0),
    "current_u_ms": (-1.5, 1.5),
    "current_v_ms": (-1.5, 1.5),
    "wave_height_m": (0.0, 4.0),
}

# Used by the trust overlay to turn a raw correction magnitude into a
# 0..1 "how big is this disagreement" score.
MAX_EXPECTED_CORRECTION = {
    "sst_c": 3.0,
    "current_u_ms": 0.6,
    "current_v_ms": 0.6,
    "wave_height_m": 1.5,
}


# ---------------------------------------------------------------------------
# Sensor network graph construction
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GraphConfig:
    # Candidate-neighbour search uses a KD-tree for tractability (O(n log n)
    # instead of O(n^2) as the sensor network grows -- same motivation as the
    # linear-time streaming design used elsewhere in VARUNA). The EDGE WEIGHTS
    # themselves, computed afterwards, are what encode real oceanographic
    # connectivity -- current alignment + depth similarity + distance decay --
    # not the raw candidate distance. See distance.py.
    k_neighbors: int = 8
    length_scale_km: float = 150.0
    depth_scale_m: float = 200.0
    # Minimum edge weight to keep (prunes near-zero, physically meaningless edges)
    min_edge_weight: float = 0.02
    # Weight blend between the pure spatial/depth decay and the current-alignment
    # boost: weight = decay * (base_flow + (1 - base_flow) * flow_factor)
    base_flow_weight: float = 0.4


GRAPH = GraphConfig()


# ---------------------------------------------------------------------------
# GNN training
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GNNConfig:
    hidden_channels: int = 32
    num_layers: int = 3
    dropout: float = 0.1
    epochs: int = 300
    lr: float = 1e-2
    weight_decay: float = 1e-5
    val_fraction: float = 0.2
    seed: int = 42
    # If a sensor network is smaller than this, GNN training is skipped and the
    # engine falls back automatically -- too few labelled nodes to trust a
    # trained model's generalisation.
    min_sensors_for_training: int = 8


GNN = GNNConfig()


# ---------------------------------------------------------------------------
# Trust overlay thresholds
# ---------------------------------------------------------------------------

TRUST_GREEN_MIN = 0.7
TRUST_AMBER_MIN = 0.4


# ---------------------------------------------------------------------------
# Data source adapters (mock now; swap to real teammate endpoints on Day 3)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SourceConfig:
    # "mock" | "http"
    model_source: str = os.getenv("VARUNA_MODEL_SOURCE", "mock")
    model_source_url: str = os.getenv("VARUNA_MODEL_SOURCE_URL", "http://localhost:8000/model")
    observation_source: str = os.getenv("VARUNA_OBS_SOURCE", "mock")
    observation_source_url: str = os.getenv("VARUNA_OBS_SOURCE_URL", "http://localhost:8000/observations")
    http_timeout_s: float = 5.0


SOURCES = SourceConfig()


# ---------------------------------------------------------------------------
# API server
# ---------------------------------------------------------------------------

API_HOST = os.getenv("VARUNA_API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("VARUNA_API_PORT", "8000"))

# Comma-separated list of origins allowed to call this API from a browser.
# Defaults cover the Vite dev server (frontend/) on its default port.
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "VARUNA_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]
