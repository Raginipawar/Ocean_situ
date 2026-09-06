"""
Builds the sensor-network graph that the Graph Fusion Engine reasons over.

Nodes:
  - "sensor" nodes: one per real in-situ reading (Argo/Glider/CTD/Buoy) from
    /observations. These are the *labelled* nodes -- we know the true bias
    (observation - model background) at each one.
  - "grid" nodes: one per model grid cell from /model. These are the
    *unlabelled* nodes whose bias we want the engine to infer.

Edges are found via a KD-tree nearest-neighbour search purely for
tractability (so the graph stays sparse as the sensor network grows, same
spirit as the linear-time streaming design used for ingestion). The edge
*weights* -- which is what actually drives the fusion correction -- come from
`distance.connectivity_weight`, i.e. real oceanographic connectivity
(current alignment + depth similarity + distance decay), not raw distance.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx
import numpy as np
from scipy.spatial import cKDTree

from . import config
from .distance import connectivity_weight
from .schemas import ModelSnapshot, ObservationSnapshot


def _project_xy(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """Local equirectangular projection to km, good enough at basin scale."""
    lat0 = float(np.mean(lat))
    x = lon * 111.32 * np.cos(np.radians(lat0))
    y = lat * 111.32
    return np.stack([x, y], axis=1)


def _normalize(value: float, lo: float, hi: float) -> float:
    return float((value - lo) / (hi - lo) * 2.0 - 1.0)


@dataclass
class FusionGraph:
    """Everything downstream engines (GNN or fallback) need, in plain arrays."""

    variables: list[str]
    node_ids: list[str]
    is_sensor: np.ndarray            # (N,) bool
    lat: np.ndarray                  # (N,)
    lon: np.ndarray                  # (N,)
    depth_m: np.ndarray              # (N,)
    background: dict[str, np.ndarray]   # var -> (N,) model background value at this node
    residual: dict[str, np.ndarray]     # var -> (N,) obs - background; NaN where unknown (grid nodes)
    features: np.ndarray             # (N, F) normalised feature matrix for the GNN
    edge_index: np.ndarray           # (2, E) int64, both directions included
    edge_weight: np.ndarray          # (E,) float32
    nx_graph: nx.Graph               # undirected, for the fallback engine + visualisation

    @property
    def n_nodes(self) -> int:
        return len(self.node_ids)

    @property
    def n_sensors(self) -> int:
        return int(self.is_sensor.sum())

    @property
    def n_grid_points(self) -> int:
        return int((~self.is_sensor).sum())

    def sensor_indices(self) -> np.ndarray:
        return np.nonzero(self.is_sensor)[0]

    def grid_indices(self) -> np.ndarray:
        return np.nonzero(~self.is_sensor)[0]


class SensorGraphBuilder:
    def __init__(self, graph_config: config.GraphConfig = config.GRAPH):
        self.cfg = graph_config

    def build(
        self,
        model: ModelSnapshot,
        obs: ObservationSnapshot,
        variables: list[str] | None = None,
    ) -> FusionGraph:
        variables = variables or config.VARIABLES

        if not model.points:
            raise ValueError("Model snapshot has no grid points")

        grid_lat = np.array([p.lat for p in model.points], dtype=np.float64)
        grid_lon = np.array([p.lon for p in model.points], dtype=np.float64)
        grid_depth = np.array([p.depth_m for p in model.points], dtype=np.float64)
        grid_xy = _project_xy(grid_lat, grid_lon)
        grid_tree = cKDTree(grid_xy)

        grid_values: dict[str, np.ndarray] = {}
        for var in variables:
            grid_values[var] = np.array(
                [getattr(p, var) if getattr(p, var) is not None else np.nan for p in model.points],
                dtype=np.float64,
            )

        n_sensors = len(obs.points)
        n_grid = len(model.points)
        n_nodes = n_sensors + n_grid

        node_ids: list[str] = [p.sensor_id for p in obs.points] + [
            f"grid_{i}" for i in range(n_grid)
        ]
        is_sensor = np.array([True] * n_sensors + [False] * n_grid)
        lat = np.concatenate(
            [np.array([p.lat for p in obs.points], dtype=np.float64), grid_lat]
        )
        lon = np.concatenate(
            [np.array([p.lon for p in obs.points], dtype=np.float64), grid_lon]
        )
        depth_m = np.concatenate(
            [np.array([p.depth_m for p in obs.points], dtype=np.float64), grid_depth]
        )

        # --- background value (the model's opinion) and residual (obs - background) ---
        background: dict[str, np.ndarray] = {}
        residual: dict[str, np.ndarray] = {}

        if n_sensors > 0:
            sensor_xy = _project_xy(
                np.array([p.lat for p in obs.points]), np.array([p.lon for p in obs.points])
            )
            _, nearest_grid_idx = grid_tree.query(sensor_xy, k=1)
            nearest_grid_idx = np.atleast_1d(nearest_grid_idx)
        else:
            nearest_grid_idx = np.array([], dtype=int)

        for var in variables:
            sensor_bg = grid_values[var][nearest_grid_idx] if n_sensors > 0 else np.array([])
            sensor_obs = np.array(
                [getattr(p, var) if getattr(p, var) is not None else np.nan for p in obs.points],
                dtype=np.float64,
            )
            bg_full = np.concatenate([sensor_bg, grid_values[var]])
            background[var] = bg_full

            res_sensor = sensor_obs - sensor_bg
            res_grid = np.full(n_grid, np.nan)
            residual[var] = np.concatenate([res_sensor, res_grid])

        # --- node features: normalised background values + position + sensor flag ---
        feature_cols = []
        for var in variables:
            lo, hi = config.VARIABLE_RANGES[var]
            col = np.clip((background[var] - lo) / (hi - lo) * 2.0 - 1.0, -3.0, 3.0)
            col = np.nan_to_num(col, nan=0.0)
            feature_cols.append(col)

        lat_norm = (lat - config.LAT_MIN) / (config.LAT_MAX - config.LAT_MIN) * 2.0 - 1.0
        lon_norm = (lon - config.LON_MIN) / (config.LON_MAX - config.LON_MIN) * 2.0 - 1.0
        depth_norm = np.clip(depth_m / 500.0, 0.0, 3.0)
        sensor_flag = is_sensor.astype(np.float64)

        features = np.stack(
            feature_cols + [lat_norm, lon_norm, depth_norm, sensor_flag], axis=1
        ).astype(np.float32)

        # --- candidate edges via KD-tree over ALL nodes ---
        all_xy = _project_xy(lat, lon)
        k = min(self.cfg.k_neighbors + 1, n_nodes)  # +1 because self is included
        tree = cKDTree(all_xy)
        _, neighbor_idx = tree.query(all_xy, k=k)
        neighbor_idx = np.atleast_2d(neighbor_idx)

        # reference current field for flow-alignment weighting
        u_bg = background.get("current_u_ms", np.zeros(n_nodes))
        v_bg = background.get("current_v_ms", np.zeros(n_nodes))

        nx_graph = nx.Graph()
        for i, nid in enumerate(node_ids):
            nx_graph.add_node(
                nid,
                index=i,
                is_sensor=bool(is_sensor[i]),
                lat=float(lat[i]),
                lon=float(lon[i]),
                depth_m=float(depth_m[i]),
            )

        edges_i: list[int] = []
        edges_j: list[int] = []
        edges_w: list[float] = []

        seen: set[tuple[int, int]] = set()
        for i in range(n_nodes):
            for j in neighbor_idx[i]:
                j = int(j)
                if j == i:
                    continue
                key = (min(i, j), max(i, j))
                if key in seen:
                    continue
                seen.add(key)

                mean_u = float((u_bg[i] + u_bg[j]) / 2.0)
                mean_v = float((v_bg[i] + v_bg[j]) / 2.0)

                cw = connectivity_weight(
                    lat1=float(lat[i]), lon1=float(lon[i]), depth1_m=float(depth_m[i]),
                    lat2=float(lat[j]), lon2=float(lon[j]), depth2_m=float(depth_m[j]),
                    mean_current_u=mean_u, mean_current_v=mean_v,
                    length_scale_km=self.cfg.length_scale_km,
                    depth_scale_m=self.cfg.depth_scale_m,
                    base_flow_weight=self.cfg.base_flow_weight,
                )
                if cw.weight < self.cfg.min_edge_weight:
                    continue

                edges_i += [i, j]
                edges_j += [j, i]
                edges_w += [cw.weight, cw.weight]

                nx_graph.add_edge(
                    node_ids[i], node_ids[j],
                    weight=cw.weight, distance_km=cw.distance_km, flow_factor=cw.flow_factor,
                )

        edge_index = np.array([edges_i, edges_j], dtype=np.int64) if edges_i else np.zeros((2, 0), dtype=np.int64)
        edge_weight = np.array(edges_w, dtype=np.float32) if edges_w else np.zeros((0,), dtype=np.float32)

        return FusionGraph(
            variables=variables,
            node_ids=node_ids,
            is_sensor=is_sensor,
            lat=lat,
            lon=lon,
            depth_m=depth_m,
            background=background,
            residual=residual,
            features=features,
            edge_index=edge_index,
            edge_weight=edge_weight,
            nx_graph=nx_graph,
        )
