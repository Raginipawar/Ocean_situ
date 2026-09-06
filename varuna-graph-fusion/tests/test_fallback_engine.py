"""
Unit tests for the training-free fallback engine, using small hand-built
graphs (bypassing SensorGraphBuilder) so the exact weighted-propagation math
can be checked precisely.
"""
import networkx as nx
import numpy as np

from graph_fusion.fallback_engine import FallbackFusionEngine
from graph_fusion.graph_builder import FusionGraph


def _tiny_graph(edges, is_sensor, residual_sst):
    n = len(is_sensor)
    node_ids = [f"n{i}" for i in range(n)]
    g = nx.Graph()
    for i, nid in enumerate(node_ids):
        g.add_node(nid, index=i, is_sensor=bool(is_sensor[i]), lat=0.0, lon=0.0, depth_m=0.0)
    for i, j, w in edges:
        g.add_edge(node_ids[i], node_ids[j], weight=w, distance_km=0.0, flow_factor=0.5)

    dummy = np.zeros(n, dtype=np.float64)
    return FusionGraph(
        variables=["sst_c"],
        node_ids=node_ids,
        is_sensor=np.array(is_sensor, dtype=bool),
        lat=dummy.copy(), lon=dummy.copy(), depth_m=dummy.copy(),
        background={"sst_c": dummy.copy()},
        residual={"sst_c": np.array(residual_sst, dtype=np.float64)},
        features=np.zeros((n, 1), dtype=np.float32),
        edge_index=np.zeros((2, 0), dtype=np.int64),
        edge_weight=np.zeros((0,), dtype=np.float32),
        nx_graph=g,
    )


def test_direct_neighbor_average_weighted_by_edge_weight():
    # node0 = sensor(+4.0), node1 = grid, node2 = sensor(-2.0); node1 sees both.
    fg = _tiny_graph(
        edges=[(0, 1, 0.8), (1, 2, 0.2)],
        is_sensor=[True, False, True],
        residual_sst=[4.0, np.nan, -2.0],
    )
    corrections, _diag = FallbackFusionEngine().predict(fg)
    expected = (0.8 * 4.0 + 0.2 * -2.0) / (0.8 + 0.2)
    assert np.isclose(corrections[1, 0], expected)


def test_sensor_node_keeps_its_own_residual():
    fg = _tiny_graph(edges=[(0, 1, 0.5)], is_sensor=[True, False], residual_sst=[3.5, np.nan])
    corrections, _diag = FallbackFusionEngine().predict(fg)
    assert corrections[0, 0] == 3.5


def test_two_hop_propagation_when_no_direct_sensor_neighbor():
    # node0 = sensor(+6.0) -- node1 = grid -- node2 = grid (target)
    fg = _tiny_graph(
        edges=[(0, 1, 0.9), (1, 2, 0.5)],
        is_sensor=[True, False, False],
        residual_sst=[6.0, np.nan, np.nan],
    )
    corrections, diag = FallbackFusionEngine().predict(fg)
    assert np.isclose(corrections[2, 0], 6.0)  # only path to any sensor is through node1
    assert diag.n_two_hop == 1


def test_isolated_node_gets_zero_correction():
    fg = _tiny_graph(
        edges=[(0, 1, 0.5)],
        is_sensor=[True, False, False],
        residual_sst=[2.0, np.nan, np.nan],
    )
    corrections, diag = FallbackFusionEngine().predict(fg)
    assert corrections[2, 0] == 0.0
    assert diag.n_isolated == 1


def test_no_sensors_at_all_yields_all_zero_corrections(sample_model):
    from graph_fusion.graph_builder import SensorGraphBuilder
    from graph_fusion.schemas import ObservationSnapshot

    empty_obs = ObservationSnapshot(region="bay_of_bengal", points=[])
    fg = SensorGraphBuilder().build(sample_model, empty_obs)
    corrections, diag = FallbackFusionEngine().predict(fg)
    assert np.all(corrections == 0.0)
    assert diag.n_isolated == fg.n_nodes
