"""
Training-free graph-weighted correction engine.

This is the fallback named explicitly in the approach doc: "fall back to the
simpler graph-weighted correction with networkx -- it's still legitimately
'graph-based fusion' under questioning." It runs automatically whenever the
GNN path is unavailable (too few sensors, unstable/NaN training loss, or an
exception of any kind) and never fails, which is what makes the "never cut
the core loop" promise possible.

For every node needing a correction, this walks the connectivity graph
outward (1-hop, then 2-hop if still isolated) and takes an edge-weight
weighted average of known sensor residuals it finds -- i.e. a graph
diffusion / weighted Nadaraya-Watson regression over the oceanographic
connectivity graph, not a plain nearest-neighbour or IDW interpolation.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .graph_builder import FusionGraph


@dataclass
class FallbackDiagnostics:
    n_one_hop: int = 0
    n_two_hop: int = 0
    n_isolated: int = 0


def build_adjacency(fg: FusionGraph) -> dict[int, list[tuple[int, float]]]:
    adjacency: dict[int, list[tuple[int, float]]] = {i: [] for i in range(fg.n_nodes)}
    for u, v, data in fg.nx_graph.edges(data=True):
        iu = fg.nx_graph.nodes[u]["index"]
        iv = fg.nx_graph.nodes[v]["index"]
        w = float(data["weight"])
        adjacency[iu].append((iv, w))
        adjacency[iv].append((iu, w))
    return adjacency


class FallbackFusionEngine:
    """Zero-training graph-weighted residual propagation. Always succeeds."""

    name = "fallback"

    def predict(self, fg: FusionGraph) -> tuple[np.ndarray, FallbackDiagnostics]:
        n_vars = len(fg.variables)
        corrections = np.zeros((fg.n_nodes, n_vars), dtype=np.float32)
        adjacency = build_adjacency(fg)
        sensor_set = set(fg.sensor_indices().tolist())

        diag = FallbackDiagnostics()

        for vi, var in enumerate(fg.variables):
            residual = fg.residual[var]
            known_sensor = {i for i in sensor_set if not np.isnan(residual[i])}

            for node_idx in range(fg.n_nodes):
                if node_idx in known_sensor:
                    corrections[node_idx, vi] = residual[node_idx]
                    continue

                acc, total_w = 0.0, 0.0
                for nb, w in adjacency[node_idx]:
                    if nb in known_sensor:
                        acc += w * residual[nb]
                        total_w += w

                if total_w > 0:
                    corrections[node_idx, vi] = acc / total_w
                    if vi == 0:
                        diag.n_one_hop += 1
                    continue

                acc2, total_w2 = 0.0, 0.0
                for nb, w1 in adjacency[node_idx]:
                    for nb2, w2 in adjacency[nb]:
                        if nb2 in known_sensor:
                            w = w1 * w2
                            acc2 += w * residual[nb2]
                            total_w2 += w

                if total_w2 > 0:
                    corrections[node_idx, vi] = acc2 / total_w2
                    if vi == 0:
                        diag.n_two_hop += 1
                else:
                    corrections[node_idx, vi] = 0.0
                    if vi == 0:
                        diag.n_isolated += 1

        return corrections, diag
