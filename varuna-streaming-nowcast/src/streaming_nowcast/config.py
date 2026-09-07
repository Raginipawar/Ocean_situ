"""
Central configuration for the VARUNA Streaming Backbone + Nowcast Engine
(Person 3 / Intelligence Core #3, stretch goal).

Scope-locked per the team's approach document and Round-2 work distribution:
  Region: Bay of Bengal (identical bounding box to Person 1's Graph Fusion
          Engine, so a grid built here lines up with /model and /fused).
  Variables: SST, Currents (u/v), Wave Height, Salinity, Chlorophyll.

Every tunable knob lives here so the pipeline can be re-scoped without
touching engine code -- same pattern as graph_fusion/config.py.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Region + grid (must match varuna-graph-fusion/src/graph_fusion/config.py so
# a grid built here can be sliced straight out of a real /model snapshot)
# ---------------------------------------------------------------------------

REGION_NAME = "bay_of_bengal"

LAT_MIN = 5.0
LAT_MAX = 22.0
LON_MIN = 80.0
LON_MAX = 100.0

GRID_RESOLUTION_DEG = 1.0

# Full 5-variable set named in the Problem Statement. "sst_c" is first and is
# the one variable the Nowcast Engine and Streaming Backbone must never drop
# -- everything else is additive, same fallback philosophy as Person 1's
# SST_ONLY_VARIABLES.
VARIABLES = [
    "sst_c",
    "current_u_ms",
    "current_v_ms",
    "wave_height_m",
    "salinity_psu",
    "chlorophyll_mg_m3",
]
SST_ONLY_VARIABLES = ["sst_c"]

# Physically-motivated ranges, used only for feature scaling (never clipped
# in output), so the LSTM/ConvLSTM see inputs roughly in [-1, 1].
VARIABLE_RANGES = {
    "sst_c": (20.0, 32.0),
    "current_u_ms": (-1.5, 1.5),
    "current_v_ms": (-1.5, 1.5),
    "wave_height_m": (0.0, 4.0),
    "salinity_psu": (30.0, 37.0),
    "chlorophyll_mg_m3": (0.0, 5.0),
}


# ---------------------------------------------------------------------------
# Streaming Backbone (Task 1.2 / Section 9 of the work brief)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StreamingConfig:
    # State vector dimensionality. Defaults to the SST-only "never cut"
    # variable so the backbone is meaningful even before other tracks land;
    # bump to len(VARIABLES) once real multi-variable readings are flowing.
    input_dim: int = 1
    hidden_dim: int = 8
    seed: int = 42
    # Bounded history kept only for introspection/demo printing -- the state
    # update itself is O(1) per step and never reprocesses this buffer.
    history_maxlen: int = 200


STREAMING = StreamingConfig()


# ---------------------------------------------------------------------------
# Mock streaming source (Task 2.1 / 2.3 -- stress-test gaps and bursts)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MockStreamConfig:
    interval_s: float = 1.0
    gap_probability: float = 0.08
    burst_probability: float = 0.08
    burst_size_max: int = 4
    seed: int = 7


MOCK_STREAM = MockStreamConfig()


# ---------------------------------------------------------------------------
# ConvLSTM Nowcast Engine (Section 10 of the work brief)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NowcastConfig:
    # 3D volume shape used when training on real Copernicus Marine data --
    # see real_ocean_data.py (TARGET_LAT/TARGET_LON/TARGET_DEPTH_IDX are the
    # source of truth; these mirror them for reference/introspection).
    # Sized for GPU-accelerated training (RTX 3050 6GB) -- finer than the
    # first CPU-only pass (0.5 degree / 6 depth levels). Training-only: the
    # saved checkpoint still runs inference on CPU (see NowcastEngine's
    # docstring on device handling).
    grid_height: int = 69    # 0.25 degree steps, LAT_MIN..LAT_MAX
    grid_width: int = 81     # 0.25 degree steps, LON_MIN..LON_MAX
    grid_depth: int = 10     # representative native GLORYS depth levels
    in_channels: int = 6     # sst, salinity, current_u, current_v, wave_height, chlorophyll
    hidden_channels: int = 24
    kernel_size: int = 3
    seq_len: int = 6        # timesteps of history fed in per prediction
    epochs: int = 500
    lr: float = 1e-3
    seed: int = 42

    # Train/val/test discipline for real time-series data: a *chronological*
    # split (earliest real days -> train, next block -> val, latest -> test)
    # rather than random/seed-based -- see nowcast_engine.py's docstring for
    # why this matters more for real data than it did for synthetic
    # sequences.
    early_stopping_patience: int = 20
    early_stopping_min_delta: float = 1e-4

    # Kept only for the synthetic_ocean.py fallback path (no real data files
    # given) -- not used when training on real Copernicus data.
    n_train_sequences: int = 64
    n_val_sequences: int = 16
    n_test_sequences: int = 16


NOWCAST = NowcastConfig()

# Hard constraint from the work brief (Section 11): this track never installs
# mamba-ssm or any compiled/CUDA-kernel dependency. Every tensor op in this
# package must run identically on CPU across Windows/Mac/Linux.
DEVICE = "cpu"


# ---------------------------------------------------------------------------
# Data source adapters (mock now; swap to real /model, /observations on Day 3
# -- see varuna-graph-fusion/DAY3_INTEGRATION.md for the same pattern)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SourceConfig:
    # "mock" | "http"
    model_source: str = os.getenv("VARUNA_MODEL_SOURCE", "mock")
    model_source_url: str = os.getenv("VARUNA_MODEL_SOURCE_URL", "http://localhost:8000/api/model")
    observation_source: str = os.getenv("VARUNA_OBS_SOURCE", "mock")
    observation_source_url: str = os.getenv("VARUNA_OBS_SOURCE_URL", "http://localhost:8000/api/observations")
    http_timeout_s: float = 5.0


SOURCES = SourceConfig()
