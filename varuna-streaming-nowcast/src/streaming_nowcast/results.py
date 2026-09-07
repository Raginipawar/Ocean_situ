"""
Persisted outputs from a training/demo run.

Metrics, the loss curve, and a predicted-vs-actual comparison are written to
`results/` at the package root so a run's evidence survives after the
process exits -- useful for the pitch deck, the backup demo video, and
answering "show me the numbers" without re-running training live.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless-safe: no display needed to render PNGs
import matplotlib.pyplot as plt
import numpy as np

from .nowcast_engine import TrainingHistory

RESULTS_DIR = Path(__file__).resolve().parents[2] / "results"


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_metrics(
    history: TrainingHistory,
    evaluation: dict[str, float],
    path: Path | str | None = None,
) -> Path:
    """Write training summary + held-out evaluation (model vs. persistence
    baseline) as JSON."""
    path = Path(path) if path else RESULTS_DIR / "nowcast_metrics.json"
    _ensure_dir(path.parent)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "best_epoch": history.best_epoch,
        "best_val_loss": history.best_val_loss,
        "stopped_early": history.stopped_early,
        "n_epochs_run": len(history.train_loss),
        "final_train_loss": history.train_loss[-1] if history.train_loss else None,
        "final_val_loss": history.val_loss[-1] if history.val_loss else None,
        "evaluation": evaluation,
    }
    path.write_text(json.dumps(payload, indent=2))
    return path


def plot_loss_curve(history: TrainingHistory, path: Path | str | None = None) -> Path:
    """Train vs. validation loss per epoch, with the selected best-checkpoint
    epoch marked -- the standard "did this actually learn" chart."""
    path = Path(path) if path else RESULTS_DIR / "nowcast_loss_curve.png"
    _ensure_dir(path.parent)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    epochs = np.arange(1, len(history.train_loss) + 1)
    ax.plot(epochs, history.train_loss, label="train loss")
    ax.plot(epochs, history.val_loss, label="val loss")
    if history.best_epoch > 0:
        ax.axvline(
            history.best_epoch, color="gray", linestyle="--", linewidth=1,
            label=f"best epoch ({history.best_epoch})",
        )
    ax.set_xlabel("epoch")
    ax.set_ylabel("MSE loss")
    ax.set_title("Nowcast Engine (ConvLSTM) training curve")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_prediction_comparison(
    actual: np.ndarray,
    predicted: np.ndarray,
    mask: np.ndarray | None = None,
    path: Path | str | None = None,
    variable_label: str = "SST (degC)",
) -> Path:
    """Actual next frame, predicted next frame, and their error -- side by
    side, same color scale for the first two so the comparison is honest.
    `actual`/`predicted` are 2D (H, W) slices; pass `mask` (H, W bool, True
    = ocean) to NaN-out land so it doesn't distort the color scale."""
    path = Path(path) if path else RESULTS_DIR / "nowcast_prediction_comparison.png"
    _ensure_dir(path.parent)

    if mask is not None:
        actual = np.where(mask, actual, np.nan)
        predicted = np.where(mask, predicted, np.nan)

    error = predicted - actual
    vmin = float(np.nanmin([actual, predicted]))
    vmax = float(np.nanmax([actual, predicted]))

    fig, axes = plt.subplots(1, 3, figsize=(13, 4))

    im0 = axes[0].imshow(actual, cmap="viridis", vmin=vmin, vmax=vmax, origin="lower")
    axes[0].set_title("Actual next frame")
    fig.colorbar(im0, ax=axes[0], label=variable_label, fraction=0.046)

    im1 = axes[1].imshow(predicted, cmap="viridis", vmin=vmin, vmax=vmax, origin="lower")
    axes[1].set_title("Nowcast prediction")
    fig.colorbar(im1, ax=axes[1], label=variable_label, fraction=0.046)

    lim = float(np.nanmax(np.abs(error))) or 1.0
    im2 = axes[2].imshow(error, cmap="coolwarm", vmin=-lim, vmax=lim, origin="lower")
    axes[2].set_title(f"Error (mean |err| = {np.nanmean(np.abs(error)):.3f})")
    fig.colorbar(im2, ax=axes[2], label=f"{variable_label} error", fraction=0.046)

    for ax in axes:
        ax.set_xlabel("lon index")
        ax.set_ylabel("lat index")

    fig.suptitle("VARUNA Nowcast Engine -- predicted vs actual")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_multi_channel_summary(
    actual_volume: np.ndarray,
    predicted_volume: np.ndarray,
    mask: np.ndarray,
    variable_names: list[str],
    depth_idx: int = 0,
    path: Path | str | None = None,
) -> Path:
    """One row per tracked variable (actual / predicted / error), all at the
    same depth level -- the "everything the model predicts, at a glance"
    artifact. `actual_volume`/`predicted_volume`: (C, D, H, W); `mask`:
    (C, D, H, W bool)."""
    path = Path(path) if path else RESULTS_DIR / "nowcast_multi_channel_summary.png"
    _ensure_dir(path.parent)

    n = len(variable_names)
    fig, axes = plt.subplots(n, 3, figsize=(11, 3 * n))
    if n == 1:
        axes = axes[None, :]

    for c, name in enumerate(variable_names):
        m = mask[c, depth_idx]
        a = np.where(m, actual_volume[c, depth_idx], np.nan)
        p = np.where(m, predicted_volume[c, depth_idx], np.nan)
        err = p - a
        vmin, vmax = float(np.nanmin([a, p])), float(np.nanmax([a, p]))

        im0 = axes[c, 0].imshow(a, cmap="viridis", vmin=vmin, vmax=vmax, origin="lower")
        axes[c, 0].set_ylabel(name, fontsize=9)
        fig.colorbar(im0, ax=axes[c, 0], fraction=0.046)

        im1 = axes[c, 1].imshow(p, cmap="viridis", vmin=vmin, vmax=vmax, origin="lower")
        fig.colorbar(im1, ax=axes[c, 1], fraction=0.046)

        lim = float(np.nanmax(np.abs(err))) or 1.0
        im2 = axes[c, 2].imshow(err, cmap="coolwarm", vmin=-lim, vmax=lim, origin="lower")
        fig.colorbar(im2, ax=axes[c, 2], fraction=0.046)

        if c == 0:
            axes[c, 0].set_title("Actual")
            axes[c, 1].set_title("Predicted")
            axes[c, 2].set_title("Error")

    fig.suptitle(f"VARUNA 3D Nowcast Engine -- all variables, depth level {depth_idx}")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path
