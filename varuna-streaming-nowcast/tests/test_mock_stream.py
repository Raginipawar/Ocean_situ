from streaming_nowcast.mock_stream import iter_mock_stream, mock_observation_point


def test_iter_mock_stream_shapes():
    readings = list(iter_mock_stream(n_steps=50, input_dim=2, seed=1))
    non_gaps = [r for r in readings if r is not None]
    assert all(len(r) == 2 for r in non_gaps)
    assert len(readings) >= 50  # bursts add extra readings


def test_iter_mock_stream_has_gaps_and_bursts_with_nonzero_probability():
    readings = list(iter_mock_stream(n_steps=300, input_dim=1, gap_probability=0.5, burst_probability=0.0, seed=2))
    n_gaps = sum(1 for r in readings if r is None)
    assert n_gaps > 0


def test_iter_mock_stream_reproducible_with_seed():
    a = list(iter_mock_stream(n_steps=30, input_dim=1, seed=7))
    b = list(iter_mock_stream(n_steps=30, input_dim=1, seed=7))
    assert a == b


def test_iter_mock_stream_rejects_input_dim_too_large():
    import pytest

    with pytest.raises(ValueError):
        list(iter_mock_stream(n_steps=5, input_dim=99))


def test_mock_observation_point_shape():
    point = mock_observation_point(step=3, seed=1)
    assert point.sst_c is not None
    assert -90 <= point.lat <= 90
    assert -180 <= point.lon <= 180
