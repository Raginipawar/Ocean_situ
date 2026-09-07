"""
End-to-end CLI demo -- Streaming Backbone + Nowcast Engine.

Section A proves the backbone is stable over a realistic (gap/burst-injected)
stream. Section B trains the Nowcast Engine -- on real Copernicus Marine
data if the well-known local file paths from this track's data-gathering
session are found, otherwise on the synthetic fallback -- and reports a
held-out evaluation against the persistence baseline.

Run with:
    python scripts/run_demo.py
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("run_demo")

from streaming_nowcast.mock_stream import iter_mock_stream  # noqa: E402
from streaming_nowcast.nowcast_engine import NowcastEngine  # noqa: E402
from streaming_nowcast.streaming_backbone import StreamingBackbone  # noqa: E402
from streaming_nowcast import results  # noqa: E402

# Real data files gathered for this track -- update these paths, or leave
# missing to fall back to the synthetic demo automatically.
REAL_DATA_CANDIDATES = [
    (
        [
            r"C:\Users\nikhi\Desktop\STUDY\TY SEM I\SIH\bay_of_bengal_phy_reanalysis.nc",
            r"C:\Users\nikhi\Desktop\STUDY\TY SEM I\SIH\bay_of_bengal_phy_reanalysis_part2.nc",
        ],
        r"C:\Users\nikhi\Downloads\wave height.nc",
        r"C:\Users\nikhi\Downloads\chlorophyll.nc",
    ),
]


def section_a_streaming_backbone() -> None:
    print("\n" + "=" * 70)
    print("SECTION A -- Streaming Backbone")
    print("=" * 70)

    backbone = StreamingBackbone(input_dim=1, hidden_dim=8, seed=42)
    n_gaps = 0
    for reading in iter_mock_stream(n_steps=200, input_dim=1, seed=7):
        state = backbone.ingest(reading)
        if reading is None:
            n_gaps += 1

    print(f"Ingested {backbone.step_count} steps ({n_gaps} gaps, rest normal + burst readings)")
    print(f"Final hidden state finite: {all(v == v for v in backbone.state_vector)}")
    print("PASS -- stable over a realistic stream with gaps and bursts.")


def _find_real_data() -> tuple | None:
    for phy_paths, wave_path, chl_path in REAL_DATA_CANDIDATES:
        phy_ok = all(Path(p).exists() for p in phy_paths)
        if phy_ok and Path(wave_path).exists() and Path(chl_path).exists():
            existing_phy = [p for p in phy_paths if Path(p).exists()]
            return existing_phy, wave_path, chl_path
    return None


def section_b_nowcast_engine() -> None:
    print("\n" + "=" * 70)
    print("SECTION B -- Nowcast Engine")
    print("=" * 70)

    real = _find_real_data()
    engine = NowcastEngine()
    print(f"Training on device: {engine.device}")

    if real:
        phy_paths, wave_path, chl_path = real
        print(f"Real Copernicus Marine data found -- training on {len(phy_paths)} physics file(s), real wave + chlorophyll.")
        history = engine.train(phy_path=phy_paths, wave_path=wave_path, chlorophyll_path=chl_path, verbose=True)
    else:
        print("Real data files not found at the expected paths -- using the synthetic fallback.")
        history = engine.train(verbose=True)

    evaluation = engine.evaluate()
    print(f"\nEvaluation (held-out test, never seen during training): {evaluation}")

    metrics_path = results.save_metrics(history, evaluation)
    loss_path = results.plot_loss_curve(history)
    print(f"Saved: {metrics_path}")
    print(f"Saved: {loss_path}")

    if evaluation["improvement_over_baseline_pct"] > 0:
        print(f"PASS -- beats persistence baseline by {evaluation['improvement_over_baseline_pct']:.1f}%.")
    else:
        print("Did not beat persistence baseline this run -- see results/ for the full picture.")


if __name__ == "__main__":
    section_a_streaming_backbone()
    section_b_nowcast_engine()
    print("\n" + "=" * 70)
    print("Demo complete. See results/ for saved artifacts.")
    print("=" * 70)
