"""
Mock streaming data source for the Streaming Backbone (Task 2.1, Task 2.3).

Real-time ingestion is owned by Person 6 (Argo/Glider/CTD/Buoy -> /observations),
whose pipeline isn't built yet, so this module emits synthetic readings
shaped exactly like what a live /observations feed would deliver, one sensor
at a time. Swapping in Person 6's real feed on Day 3 is a one-line adapter
change, same pattern as varuna-graph-fusion/src/graph_fusion/adapters.py.

"As genuine as possible" in the meantime: each reading is anchored in
Person 4's real (pre-regrid-bug) local-demo Bay-of-Bengal grid via
`real_data.sample_point()` -- the sensor's spatial value is genuine model
output, not an invented formula. No track has a real *time series* yet
(that's the whole point of this component -- it's the one demonstrating
streaming behaviour before anyone else's does), so a smooth, small-amplitude
temporal fluctuation plus realistic instrument noise is layered on top of
that real spatial anchor to produce a live-feeling stream. Noise magnitudes
match varuna-graph-fusion/src/graph_fusion/mock_data.py's observation noise
model, for consistency across the team's mocks.

Also implements the Day 2 stress-test requirements (Task 2.3): a configurable
fraction of steps are dropped as gaps (missing timestep), and a configurable
fraction arrive as bursts of several readings in immediate succession.
"""
from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

import numpy as np

from . import config, real_data
from .schemas import ObservationPoint, SensorType

# Same noise model as graph_fusion/mock_data.py's generate_mock_observations,
# extended to the two additional variables this track's config tracks.
_NOISE_STD = {
    "sst_c": 0.15,
    "current_u_ms": 0.03,
    "current_v_ms": 0.03,
    "wave_height_m": 0.08,
    "salinity_psu": 0.05,
    "chlorophyll_mg_m3": 0.02,
}

# Slow-drift amplitude per variable -- small relative to real spatial
# variation, standing in for short-term physical fluctuation (e.g. a diurnal
# SST cycle) until a real time-series source exists.
_DRIFT_AMPLITUDE = {
    "sst_c": 0.3,
    "current_u_ms": 0.02,
    "current_v_ms": 0.02,
    "wave_height_m": 0.1,
    "salinity_psu": 0.05,
    "chlorophyll_mg_m3": 0.02,
}

DEFAULT_SENSOR_LAT = 13.0
DEFAULT_SENSOR_LON = 88.0


def _reading_value(variable: str, step: int, lat: float, lon: float, rng: np.random.Generator) -> float:
    """Real spatial anchor (Person 4's grid) + simulated temporal drift +
    realistic sensor noise. See module docstring for why each part exists."""
    base = real_data.sample_point(lat, lon, variable)
    drift = _DRIFT_AMPLITUDE[variable] * np.sin(step / 20.0)
    noise = rng.normal(0.0, _NOISE_STD[variable])
    return float(base + drift + noise)


def iter_mock_stream(
    n_steps: int,
    input_dim: int = 1,
    lat: float = DEFAULT_SENSOR_LAT,
    lon: float = DEFAULT_SENSOR_LON,
    gap_probability: float | None = None,
    burst_probability: float | None = None,
    burst_size_max: int | None = None,
    seed: int | None = None,
) -> Iterator[list[float] | None]:
    """Yield readings shaped for `StreamingBackbone.ingest()`.

    Each yielded item is a length-`input_dim` list of floats (one entry per
    leading variable in `config.VARIABLES`, real-data-anchored as described
    above), or `None` for a gap (a missing timestep). A step that rolls a
    "burst" also yields several extra readings immediately afterward,
    arriving in order with no gap between them -- Task 2.3's two stress
    cases.
    """
    if input_dim > len(config.VARIABLES):
        raise ValueError(f"input_dim={input_dim} exceeds the tracked variable set ({len(config.VARIABLES)})")
    variables = config.VARIABLES[:input_dim]

    cfg = config.MOCK_STREAM
    gap_p = cfg.gap_probability if gap_probability is None else gap_probability
    burst_p = cfg.burst_probability if burst_probability is None else burst_probability
    burst_max = cfg.burst_size_max if burst_size_max is None else burst_size_max
    rng = np.random.default_rng(cfg.seed if seed is None else seed)

    for step in range(n_steps):
        if rng.random() < gap_p:
            yield None
            continue

        yield [_reading_value(v, step, lat, lon, rng) for v in variables]

        if rng.random() < burst_p:
            burst_n = int(rng.integers(1, burst_max + 1))
            for _ in range(burst_n):
                yield [_reading_value(v, step, lat, lon, rng) for v in variables]


def mock_observation_point(
    step: int,
    sensor_id: str = "mock-argo-001",
    lat: float = DEFAULT_SENSOR_LAT,
    lon: float = DEFAULT_SENSOR_LON,
    seed: int | None = None,
) -> ObservationPoint:
    """A single reading in full `/observations` shape, for callers that need
    the whole schema (e.g. handing a reading off to another track) rather
    than the raw `list[float]` the backbone itself consumes."""
    rng = np.random.default_rng((config.MOCK_STREAM.seed if seed is None else seed) + step)
    return ObservationPoint(
        sensor_id=sensor_id,
        sensor_type=SensorType.ARGO,
        lat=lat,
        lon=lon,
        depth_m=0.0,
        time=datetime.now(timezone.utc) + timedelta(seconds=step),
        sst_c=_reading_value("sst_c", step, lat, lon, rng),
    )
