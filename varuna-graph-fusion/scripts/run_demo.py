"""
End-to-end CLI demo of the Graph Fusion Engine -- no API server, no frontend,
just: generate mock /model + /observations, run both engines, and print a
judge-readable before/after report.

Usage:
    python scripts/run_demo.py
    python scripts/run_demo.py --n-sensors 60 --resolution 0.5
    python scripts/run_demo.py --engine fallback
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from graph_fusion import config, mock_data  # noqa: E402
from graph_fusion.fusion_service import FusionService  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="VARUNA Graph Fusion Engine demo")
    parser.add_argument("--n-sensors", type=int, default=40)
    parser.add_argument("--resolution", type=float, default=config.GRID_RESOLUTION_DEG)
    parser.add_argument("--engine", choices=["auto", "gnn", "fallback"], default="auto")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--top", type=int, default=8, help="How many sensor corrections to list")
    args = parser.parse_args()

    print("=" * 78)
    print("VARUNA -- Graph Fusion Engine demo (Person 1 / Intelligence Core #1)")
    print(f"Region: {config.REGION_NAME}   Variables: {', '.join(config.VARIABLES)}")
    print("=" * 78)

    t0 = time.perf_counter()
    model = mock_data.generate_mock_model_grid(resolution_deg=args.resolution)
    obs = mock_data.generate_mock_observations(n_sensors=args.n_sensors, seed=args.seed)
    print(f"\n[1/3] Generated mock data in {(time.perf_counter() - t0)*1000:.0f} ms")
    print(f"      /model        -> {len(model.points)} grid points @ {args.resolution} deg resolution")
    print(f"      /observations -> {len(obs.points)} real-sensor readings "
          f"({', '.join(sorted({p.sensor_type.value for p in obs.points}))})")

    service = FusionService()
    t0 = time.perf_counter()
    result = service.fuse(model, obs, engine=args.engine)
    elapsed = (time.perf_counter() - t0) * 1000

    s = result.summary
    print(f"\n[2/3] Fusion complete in {elapsed:.0f} ms using the '{s.engine}' engine")
    print(f"      graph: {s.n_sensors} sensor nodes + {s.n_grid_points} grid nodes, {s.n_graph_edges} edges")
    print(f"      mean confidence (trust overlay): {s.mean_confidence:.2f}")
    print(f"      mean |SST correction| across the grid: {s.mean_abs_correction_sst_c:.2f} C")
    if s.validation_mae_sst_c is not None:
        print(f"      held-out sensor validation MAE (SST): {s.validation_mae_sst_c:.2f} C")
        print("      (leave-some-sensors-out cross-validation: these sensors' labels were")
        print("       hidden from training; this is the model recovering them from graph")
        print("       context alone -- the same regime it must generalise into on the grid)")

    trust_counts = {lbl: 0 for lbl in ("green", "amber", "red")}
    for p in result.points:
        trust_counts[p.trust_label] += 1
    print(f"\n      trust overlay -> green={trust_counts['green']}  "
          f"amber={trust_counts['amber']}  red={trust_counts['red']}")

    sensor_points = [p for p in result.points if p.is_sensor_node]
    sensor_points.sort(key=lambda p: abs(p.correction_sst_c or 0.0), reverse=True)

    print(f"\n[3/3] Top {args.top} largest model-vs-reality SST disagreements (real sensors):")
    print(f"      {'lat':>7} {'lon':>7} {'type':>10} {'correction':>11} {'trust':>7} {'confidence':>10}")
    for p in sensor_points[: args.top]:
        sensor_id = next((o.sensor_type.value for o in obs.points
                           if abs(o.lat - p.lat) < 1e-6 and abs(o.lon - p.lon) < 1e-6), "?")
        print(f"      {p.lat:7.2f} {p.lon:7.2f} {sensor_id:>10} "
              f"{p.correction_sst_c:+10.2f}C {p.trust_label:>7} {p.confidence:10.2f}")

    print("\nThis is the live signal VARUNA's trust overlay renders on the 3D globe, and")
    print("the same residual the Drift Memory Engine (Person 2) turns into alerts.")
    print("=" * 78)


if __name__ == "__main__":
    main()
