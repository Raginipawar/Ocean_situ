"""
Best-effort training run: stacked 2-layer ConvLSTM on the full 270 real days
gathered for this track (the original 90-day window + the 180-day
extension), GPU-accelerated if available.

Run with:
    python scripts/train_best.py
"""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

logging.basicConfig(level=logging.INFO, format="%(message)s")

from streaming_nowcast.nowcast_engine import NowcastEngine  # noqa: E402
from streaming_nowcast import results, real_ocean_data  # noqa: E402

PHY_PATHS = [
    r"C:\Users\nikhi\Desktop\STUDY\TY SEM I\SIH\bay_of_bengal_phy_reanalysis.nc",
    r"C:\Users\nikhi\Desktop\STUDY\TY SEM I\SIH\bay_of_bengal_phy_reanalysis_part2.nc",
]
WAVE_PATH = r"C:\Users\nikhi\Downloads\wave height.nc"
CHLOROPHYLL_PATH = r"C:\Users\nikhi\Downloads\chlorophyll.nc"


def main() -> None:
    engine = NowcastEngine(hidden_channels=24, num_layers=2)
    n_params = sum(p.numel() for p in engine.model.parameters())
    print(f"device: {engine.device}   params: {n_params:,}")

    t0 = time.time()
    history = engine.train(
        phy_path=PHY_PATHS,
        wave_path=WAVE_PATH,
        chlorophyll_path=CHLOROPHYLL_PATH,
        patience=30,
        batch_size=6,
        max_seconds=3300,  # 55 min -- 5 min safety margin under a 1-hour budget
        log_every=1,
        verbose=True,
    )
    print(f"training took {time.time() - t0:.1f} seconds")

    evaluation = engine.evaluate()
    print("FINAL EVALUATION:", evaluation)

    x_test, y_test = engine._test_cache
    last_window = x_test[-1].numpy() * engine.channel_std[0] + engine.channel_mean[0]
    actual_next = y_test[-1].numpy() * engine.channel_std[0] + engine.channel_mean[0]
    predicted_next = engine.predict(last_window)

    metrics_path = results.save_metrics(history, evaluation)
    loss_path = results.plot_loss_curve(history)
    summary_path = results.plot_multi_channel_summary(
        actual_next, predicted_next, engine.mask, real_ocean_data.VARIABLES, depth_idx=0
    )
    sst_path = results.plot_prediction_comparison(
        actual_next[0, 0], predicted_next[0, 0], mask=engine.mask[0, 0],
        path=results.RESULTS_DIR / "nowcast_sst_surface_comparison.png",
        variable_label="SST (degC)",
    )
    engine.save(str(results.RESULTS_DIR / "nowcast_model.pt"))

    print("Saved:", metrics_path)
    print("Saved:", loss_path)
    print("Saved:", summary_path)
    print("Saved:", sst_path)
    print("ALL ARTIFACTS SAVED")


if __name__ == "__main__":
    main()
