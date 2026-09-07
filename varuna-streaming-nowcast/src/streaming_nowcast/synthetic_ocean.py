"""
Time-evolving training/demo sequences for the ConvLSTM Nowcast Engine.

No track owns real *time-series* gridded ocean data yet -- Person 4's
pipeline (see real_data.py) hands over one real, physically-plausible
Bay-of-Bengal snapshot, not a sequence, and that's expected at this stage of
the build (Section 10 of the work brief: "training data ... can run against
mock grids if real data isn't stable yet"). This module keeps the *spatial*
structure genuine (every frame starts from Person 4's real base grid) and
simulates only the *temporal* evolution: a localized warm/cool anomaly patch
drifting across the field at a constant velocity -- a deliberately simple
stand-in for real mesoscale advection, in the same spirit as
varuna-graph-fusion/src/graph_fusion/mock_data.py's synthetic "marine
heatwave" patch (reused here on purpose, for a consistent story across the
team's tracks: Person 1 simulates a *spatial* model/reality gap with a
heatwave patch, this track simulates the *temporal* evolution of one).

The moment Person 4's pipeline (or anyone's) produces a real multi-timestep
feed, `generate_sequence` is the only function that needs to change --
everything downstream (ConvLSTM, NowcastEngine) already consumes a plain
(T, H, W) array and doesn't know or care where it came from.
"""
from __future__ import annotations

import numpy as np

from . import real_data


def generate_sequence(
    n_steps: int,
    variable: str = "sst_c",
    seed: int | None = None,
    anomaly_amplitude: float = 2.0,
    anomaly_radius_deg: float = 3.0,
    drift_speed_deg_per_step: float = 0.45,
    noise_std: float = 0.008,
) -> np.ndarray:
    """One (n_steps, H, W) sequence: Person 4's real base grid for `variable`
    plus a drifting localized anomaly plus small per-step noise.

    Amplitude (2.0 degC) is deliberately close to Person 1's own synthetic
    "marine heatwave" peak (2.2 degC in graph_fusion/mock_data.py) -- a
    believable mesoscale-anomaly magnitude, not a number picked to make the
    model look good. `noise_std` reflects a gridded model-output field
    (smoother by construction) rather than a raw noisy point sensor reading
    (contrast mock_stream.py's larger observation noise, e.g. 0.15 degC for
    a single Argo-like reading). These two together set how much of the
    frame-to-frame change is genuinely learnable temporal structure (the
    drifting anomaly) versus irreducible per-step noise a persistence
    baseline cannot help predicting either -- picked so the deterministic
    signal clearly dominates the noise floor (roughly 7x, verified
    empirically), which is what makes a *trained* model able to beat
    persistence at all, rather than the task being unfairly easy or
    unfairly impossible."""
    rng = np.random.default_rng(seed)
    base = real_data.real_base_grid(variable)
    lat, lon = real_data.target_grid_axes()
    lon_grid, lat_grid = np.meshgrid(lon, lat)

    # Random-but-plausible starting point, heading, and sign for the
    # anomaly, kept well inside the domain so it doesn't just drift off
    # the edge on step 1.
    margin = min(anomaly_radius_deg, (lat.max() - lat.min()) / 3)
    start_lat = rng.uniform(lat.min() + margin, lat.max() - margin)
    start_lon = rng.uniform(lon.min() + margin, lon.max() - margin)
    heading = rng.uniform(0, 2 * np.pi)
    v_lat = drift_speed_deg_per_step * np.sin(heading)
    v_lon = drift_speed_deg_per_step * np.cos(heading)
    amplitude = rng.choice([-1.0, 1.0]) * anomaly_amplitude * rng.uniform(0.6, 1.0)

    frames = np.empty((n_steps, *base.shape), dtype=np.float32)
    for t in range(n_steps):
        center_lat = start_lat + v_lat * t
        center_lon = start_lon + v_lon * t
        r2 = (lat_grid - center_lat) ** 2 + (lon_grid - center_lon) ** 2
        anomaly = amplitude * np.exp(-r2 / (2 * anomaly_radius_deg**2))
        noise = rng.normal(0.0, noise_std, size=base.shape)
        frames[t] = base + anomaly + noise
    return frames


def generate_dataset(
    n_sequences: int,
    n_steps: int,
    variable: str = "sst_c",
    seed: int | None = None,
) -> np.ndarray:
    """`n_sequences` independent (n_steps, H, W) sequences stacked as
    (n_sequences, n_steps, H, W) -- training diversity so the ConvLSTM learns
    "a warm patch drifts smoothly" rather than memorizing one exact path."""
    rng = np.random.default_rng(seed)
    sequences = [
        generate_sequence(n_steps, variable=variable, seed=int(rng.integers(0, 2**31 - 1)))
        for _ in range(n_sequences)
    ]
    return np.stack(sequences)
