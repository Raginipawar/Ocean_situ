import math

import pytest
import torch

from streaming_nowcast.streaming_backbone import StreamingBackbone, lstm_state_update


def test_lstm_state_update_shapes_and_finiteness():
    hidden_dim = 6
    input_dim = 3
    weight = torch.randn(4 * hidden_dim, hidden_dim + input_dim) * 0.1
    bias = torch.zeros(4 * hidden_dim)
    h0 = torch.zeros(hidden_dim)
    c0 = torch.zeros(hidden_dim)
    x = torch.randn(input_dim)

    h1, c1 = lstm_state_update(x, h0, c0, weight, bias)

    assert h1.shape == (hidden_dim,)
    assert c1.shape == (hidden_dim,)
    assert torch.isfinite(h1).all()
    assert torch.isfinite(c1).all()


def test_backbone_ingest_normal_stream_stays_finite_and_bounded():
    backbone = StreamingBackbone(input_dim=1, hidden_dim=8, seed=1)
    for t in range(100):
        state = backbone.ingest([20.0 + math.sin(t / 5.0)])
    assert all(v == v for v in state.hidden_state)  # no NaN
    assert all(abs(v) < 10.0 for v in state.hidden_state)  # bounded (tanh/sigmoid gated)


def test_backbone_gap_leaves_state_unchanged():
    backbone = StreamingBackbone(input_dim=1, hidden_dim=4, seed=2)
    backbone.ingest([25.0])
    before = backbone.state_vector
    state = backbone.ingest(None)
    assert state.was_gap is True
    assert backbone.state_vector == before


def test_backbone_burst_processes_all_in_order():
    backbone = StreamingBackbone(input_dim=1, hidden_dim=4, seed=3)
    states = backbone.ingest_batch([[1.0], [2.0], [3.0]])
    assert [s.step for s in states] == [1, 2, 3]
    assert backbone.step_count == 3


def test_backbone_sanitizes_nan_field():
    backbone = StreamingBackbone(input_dim=1, hidden_dim=4, seed=4)
    state = backbone.ingest([float("nan")])
    assert all(v == v for v in state.hidden_state)


def test_backbone_rejects_wrong_input_dim():
    backbone = StreamingBackbone(input_dim=2, hidden_dim=4, seed=5)
    with pytest.raises(ValueError):
        backbone.ingest([1.0])


def test_backbone_deterministic_given_same_seed():
    a = StreamingBackbone(input_dim=1, hidden_dim=4, seed=99)
    b = StreamingBackbone(input_dim=1, hidden_dim=4, seed=99)
    for x in [[1.0], [2.0], [3.0]]:
        sa = a.ingest(x)
        sb = b.ingest(x)
        assert sa.hidden_state == sb.hidden_state
