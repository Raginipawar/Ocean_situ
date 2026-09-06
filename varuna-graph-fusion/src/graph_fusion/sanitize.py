"""
Filters physically-implausible values out of /model and /observations before
they reach the graph, so they read as *missing* (None) rather than as real
data that skews the fusion correction.

Two distinct failure modes this catches, both structurally valid JSON (so
`ingest.py`'s per-point parsing lets them through -- a `float` is a `float`
whether it's 28.4 or a QC fill value):

1. QC/sentinel fill values -- real oceanographic feeds commonly use -999,
   -9999, etc. to mean "no reading," not zero and not a real measurement.
2. Genuinely out-of-range values from a miscalibrated sensor (SST of 85C).

`PHYSICAL_LIMITS` here is deliberately much wider than
`config.VARIABLE_RANGES` -- that one is a *typical Bay-of-Bengal* range used
only for ML feature normalisation (a real cold-core eddy could legitimately
sit outside it); this is "could this value possibly be real anywhere in the
ocean."
"""
from __future__ import annotations

import logging

from .schemas import ModelSnapshot, ObservationSnapshot

logger = logging.getLogger("graph_fusion.sanitize")

_SENTINELS = {-999.0, -999.9, -9999.0, -9999.9, 9999.0, 9999.9, -32768.0}

PHYSICAL_LIMITS: dict[str, tuple[float, float]] = {
    "sst_c": (-2.0, 40.0),
    "current_u_ms": (-5.0, 5.0),
    "current_v_ms": (-5.0, 5.0),
    "wave_height_m": (0.0, 20.0),
}

_VARIABLES = tuple(PHYSICAL_LIMITS.keys())


def _clean_value(var: str, value: float | None) -> float | None:
    if value is None:
        return None
    if value in _SENTINELS:
        return None
    lo, hi = PHYSICAL_LIMITS.get(var, (float("-inf"), float("inf")))
    if value < lo or value > hi:
        return None
    return value


def sanitize_model(model: ModelSnapshot) -> tuple[ModelSnapshot, int]:
    """Mutates `model.points` in place; returns (model, n_values_sanitized)."""
    n_sanitized = 0
    for point in model.points:
        for var in _VARIABLES:
            current = getattr(point, var)
            cleaned = _clean_value(var, current)
            if cleaned != current:
                n_sanitized += 1
                setattr(point, var, cleaned)
    if n_sanitized:
        logger.warning("Sanitized %d out-of-range /model value(s)", n_sanitized)
    return model, n_sanitized


def sanitize_observations(obs: ObservationSnapshot) -> tuple[ObservationSnapshot, int]:
    """Mutates `obs.points` in place; returns (obs, n_values_sanitized)."""
    n_sanitized = 0
    for point in obs.points:
        for var in _VARIABLES:
            current = getattr(point, var)
            cleaned = _clean_value(var, current)
            if cleaned != current:
                n_sanitized += 1
                setattr(point, var, cleaned)
    if n_sanitized:
        logger.warning("Sanitized %d out-of-range /observations value(s)", n_sanitized)
    return obs, n_sanitized
