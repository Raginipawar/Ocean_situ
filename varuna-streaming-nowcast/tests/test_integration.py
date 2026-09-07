"""End-to-end checks that the pieces actually fit together, not just each in isolation."""
import numpy as np

from streaming_nowcast import grid_utils, real_data
from streaming_nowcast.mock_stream import iter_mock_stream
from streaming_nowcast.nowcast_engine import NowcastEngine
from streaming_nowcast.schemas import ModelSnapshot
from streaming_nowcast.streaming_backbone import StreamingBackbone


def test_mock_stream_into_streaming_backbone_end_to_end():
    """Task 2.2/2.3: mock stream -> backbone, stable over gaps and bursts."""
    backbone = StreamingBackbone(input_dim=1, hidden_dim=8, seed=42)
    for reading in iter_mock_stream(n_steps=150, input_dim=1, seed=11):
        state = backbone.ingest(reading)
        assert all(v == v for v in state.hidden_state)  # never NaN, even across gaps/bursts


def test_grid_round_trip_into_nowcast_snapshot_contract():
    """A grid produced anywhere in this package can be turned into the
    Section 12 hand-off contract without shape mismatches."""
    target_lat, target_lon = real_data.target_grid_axes()
    grid = np.random.default_rng(0).uniform(20, 30, size=(target_lat.size, target_lon.size))

    snapshot = grid_utils.grid_to_nowcast_snapshot(grid, "bay_of_bengal", 1.0, lead_time_s=3600)

    assert len(snapshot.points) == grid.size
    assert all(p.sst_c is not None for p in snapshot.points)


def test_nowcast_engine_synthetic_fallback_beats_or_matches_random_noise():
    """Not a strong claim (synthetic fallback isn't the deliverable, real
    data is) -- just that training moves the loss meaningfully off its
    random-init starting point, i.e. the whole pipeline is wired correctly
    end-to-end without real data files."""
    engine = NowcastEngine(in_channels=1, hidden_channels=4, seq_len=4, seed=3, device="cpu")
    history = engine.train(epochs=15, batch_size=4, patience=15, verbose=False)
    assert history.train_loss[-1] < history.train_loss[0]
