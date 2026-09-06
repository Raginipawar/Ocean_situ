import numpy as np

from graph_fusion.graph_builder import SensorGraphBuilder


def test_node_counts_match_inputs(sample_model, sample_obs):
    fg = SensorGraphBuilder().build(sample_model, sample_obs)
    assert fg.n_sensors == len(sample_obs.points)
    assert fg.n_grid_points == len(sample_model.points)
    assert fg.n_nodes == fg.n_sensors + fg.n_grid_points


def test_graph_has_edges_and_symmetric_edge_index(sample_model, sample_obs):
    fg = SensorGraphBuilder().build(sample_model, sample_obs)
    assert fg.edge_index.shape[1] > 0
    # every (i, j) should have a matching (j, i)
    pairs = set(map(tuple, fg.edge_index.T.tolist()))
    for i, j in pairs:
        assert (j, i) in pairs
    assert fg.edge_weight.shape[0] == fg.edge_index.shape[1]


def test_edge_weights_are_bounded(sample_model, sample_obs):
    fg = SensorGraphBuilder().build(sample_model, sample_obs)
    assert np.all(fg.edge_weight > 0.0)
    assert np.all(fg.edge_weight <= 1.0)


def test_sensor_nodes_have_known_residual_grid_nodes_do_not(sample_model, sample_obs):
    fg = SensorGraphBuilder().build(sample_model, sample_obs)
    sst_residual = fg.residual["sst_c"]
    sensor_idx = fg.sensor_indices()
    grid_idx = fg.grid_indices()
    assert not np.any(np.isnan(sst_residual[sensor_idx]))
    assert np.all(np.isnan(sst_residual[grid_idx]))


def test_feature_matrix_shape(sample_model, sample_obs):
    variables = ["sst_c", "current_u_ms"]
    fg = SensorGraphBuilder().build(sample_model, sample_obs, variables=variables)
    # len(variables) background columns + lat + lon + depth + is_sensor flag
    assert fg.features.shape == (fg.n_nodes, len(variables) + 4)


def test_empty_observations_still_builds_a_graph(sample_model):
    from graph_fusion.schemas import ObservationSnapshot

    empty_obs = ObservationSnapshot(region="bay_of_bengal", points=[])
    fg = SensorGraphBuilder().build(sample_model, empty_obs)
    assert fg.n_sensors == 0
    assert fg.n_grid_points == len(sample_model.points)
