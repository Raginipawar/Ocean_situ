"""
Renders the sensor connectivity graph + trust overlay to a PNG, so the team
has a visual artifact for the pitch deck / backup video before Day 4's
CesiumJS scene exists.

Usage:
    python scripts/visualize_graph.py
    python scripts/visualize_graph.py --n-sensors 60 --out data/sample/graph.png
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

from graph_fusion import mock_data  # noqa: E402
from graph_fusion.fusion_service import FusionService  # noqa: E402
from graph_fusion.graph_builder import SensorGraphBuilder  # noqa: E402

TRUST_COLORS = {"green": "#2ecc71", "amber": "#f39c12", "red": "#e74c3c"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Visualize the fusion sensor graph")
    parser.add_argument("--n-sensors", type=int, default=40)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out", default="data/sample/sensor_graph.png")
    args = parser.parse_args()

    model = mock_data.generate_mock_model_grid()
    obs = mock_data.generate_mock_observations(n_sensors=args.n_sensors, seed=args.seed)

    fg = SensorGraphBuilder().build(model, obs)
    result = FusionService().fuse(model, obs, engine="auto")

    fig, ax = plt.subplots(figsize=(9, 9))

    for u, v, data in fg.nx_graph.edges(data=True):
        lat_u, lon_u = fg.nx_graph.nodes[u]["lat"], fg.nx_graph.nodes[u]["lon"]
        lat_v, lon_v = fg.nx_graph.nodes[v]["lat"], fg.nx_graph.nodes[v]["lon"]
        ax.plot(
            [lon_u, lon_v], [lat_u, lat_v],
            color="gray", linewidth=0.6 * data["weight"], alpha=0.25, zorder=1,
        )

    grid_points = [p for p in result.points if not p.is_sensor_node]
    ax.scatter(
        [p.lon for p in grid_points], [p.lat for p in grid_points],
        c=[TRUST_COLORS[p.trust_label] for p in grid_points],
        s=10, alpha=0.55, zorder=2,
    )

    sensor_points = [p for p in result.points if p.is_sensor_node]
    ax.scatter(
        [p.lon for p in sensor_points], [p.lat for p in sensor_points],
        c=[TRUST_COLORS[p.trust_label] for p in sensor_points],
        s=100, edgecolors="black", linewidths=1.1, zorder=3,
    )

    ax.set_xlabel("Longitude (deg E)")
    ax.set_ylabel("Latitude (deg N)")
    ax.set_title(
        "VARUNA Graph Fusion Engine\nsensor connectivity graph + trust overlay "
        f"(engine={result.summary.engine}, mock Bay of Bengal demo data)"
    )
    ax.set_aspect("equal")

    legend_handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor=color,
               markeredgecolor="black", markersize=9, label=f"{label} (small = grid, large = sensor)")
        for label, color in TRUST_COLORS.items()
    ]
    ax.legend(handles=legend_handles, loc="upper right", fontsize=8, title="Trust overlay")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    print(f"Saved: {out_path.resolve()}")


if __name__ == "__main__":
    main()
