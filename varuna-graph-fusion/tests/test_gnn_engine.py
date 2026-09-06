import numpy as np
import pytest

from graph_fusion import config, mock_data
from graph_fusion.graph_builder import SensorGraphBuilder
from graph_fusion.gnn_engine import GNNFusionEngine


def test_raises_when_too_few_sensors(sample_model):
    obs = mock_data.generate_mock_observations(n_sensors=3, seed=1)
    fg = SensorGraphBuilder().build(sample_model, obs)
    with pytest.raises(RuntimeError):
        GNNFusionEngine().fit_predict(fg)


def test_fit_predict_shape_and_diagnostics(sample_model, sample_obs):
    fg = SensorGraphBuilder().build(sample_model, sample_obs)
    fast_cfg = config.GNNConfig(epochs=60, hidden_channels=16, num_layers=2)
    corrections, diag = GNNFusionEngine(fast_cfg).fit_predict(fg)
    assert corrections.shape == (fg.n_nodes, len(fg.variables))
    assert diag.n_train_sensors + diag.n_val_sensors == fg.n_sensors
    assert "sst_c" in diag.val_mae


def test_gnn_beats_naive_zero_baseline_on_held_out_sensors():
    """
    The mock data has a genuine, learnable signal (the heatwave patch). A GNN
    that has actually learned to propagate residuals through the graph should
    land closer to the true held-out residual than the naive "assume the
    model is always right" (zero correction) baseline.
    """
    model = mock_data.generate_mock_model_grid(resolution_deg=2.0)
    obs = mock_data.generate_mock_observations(n_sensors=60, seed=5, heatwave_fraction=0.3)
    fg = SensorGraphBuilder().build(model, obs, variables=["sst_c"])

    fast_cfg = config.GNNConfig(
        epochs=150, hidden_channels=24, num_layers=2, val_fraction=0.3, seed=0
    )
    _corrections, diag = GNNFusionEngine(fast_cfg).fit_predict(fg)
    val_mae = diag.val_mae["sst_c"]

    residual = fg.residual["sst_c"]
    sensor_idx = fg.sensor_indices()
    naive_mae = float(np.mean(np.abs(residual[sensor_idx])))

    assert val_mae < naive_mae
