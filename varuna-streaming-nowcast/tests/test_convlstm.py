import torch

from streaming_nowcast.convlstm import ConvLSTMCell, ConvLSTMPredictor


def test_convlstm_cell_shapes():
    cell = ConvLSTMCell(in_channels=2, hidden_channels=4, kernel_size=3)
    h, c = cell.init_state(batch_size=1, depth=3, height=5, width=6, device="cpu")
    x = torch.randn(1, 2, 3, 5, 6)

    h2, c2 = cell(x, h, c)

    assert h2.shape == (1, 4, 3, 5, 6)
    assert c2.shape == (1, 4, 3, 5, 6)
    assert torch.isfinite(h2).all()
    assert torch.isfinite(c2).all()


def test_convlstm_predictor_output_shape_matches_input_channels():
    model = ConvLSTMPredictor(in_channels=3, hidden_channels=4, kernel_size=3)
    sequence = torch.randn(2, 5, 3, 4, 6, 7)  # (batch, time, channels, depth, height, width)

    out = model(sequence)

    assert out.shape == (2, 3, 4, 6, 7)
    assert torch.isfinite(out).all()


def test_convlstm_predictor_residual_matches_last_frame_at_init():
    """At initialization, the readout conv is near-zero, so the prediction
    should start close to the persistence baseline (last observed frame) --
    the whole point of the residual design (see convlstm.py's docstring)."""
    torch.manual_seed(0)
    model = ConvLSTMPredictor(in_channels=1, hidden_channels=4, kernel_size=3)
    sequence = torch.randn(1, 3, 1, 2, 5, 5)

    out = model(sequence)
    last_frame = sequence[:, -1]

    assert torch.allclose(out, last_frame, atol=1.0)
