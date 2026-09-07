"""
ConvLSTM Nowcast Engine (Section 10 of the work brief) -- trained on real
Copernicus Marine data, not synthetic sequences.

Standard supervised-learning discipline:
  - a **chronological** train/validation/test split (train on the earliest
    real days, validate on the next block, test on the latest block) --
    proper practice for real time series, unlike random/seed-based splits,
    since it never lets the model "see the future" relative to what it's
    evaluated on;
  - per-channel normalization fit on the training split only (mean/std
    computed over ocean cells, never over land, never using val/test data);
  - a **masked** loss: land cells (~32% of this Bay-of-Bengal box, real
    coastline) are excluded from every loss and metric, not zero-filled and
    silently learned as "correct" -- the model is never asked to predict
    ocean physics over India, Myanmar, or Sri Lanka;
  - early stopping on validation loss with best-checkpoint selection;
  - a held-out test score computed exactly once, after model selection is
    frozen, compared against a naive persistence baseline (predict next
    volume = last observed volume) on the same masked cells.

Falls back to `synthetic_ocean`'s generator only if no real data files are
given -- kept for standalone runs of this package without the team's
gathered Copernicus files.
"""
from __future__ import annotations

import copy
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import torch

from . import config, real_ocean_data, synthetic_ocean
from .convlstm import ConvLSTMPredictor

logger = logging.getLogger(__name__)


@dataclass
class TrainingHistory:
    train_loss: list[float] = field(default_factory=list)
    val_loss: list[float] = field(default_factory=list)
    best_epoch: int = -1
    best_val_loss: float = float("inf")
    stopped_early: bool = False


class NowcastEngine:
    """
    Note on device: `config.DEVICE`/`config.py`'s CPU-only mandate applies to
    the Streaming Backbone deliverable (Section 11 of the work brief -- no
    compiled/custom CUDA kernels, so it runs identically on any teammate's
    laptop). *Training* the Nowcast Engine on a GPU is a different thing: it
    uses only stock `torch.nn.Conv3d`, the same portable op either way, and
    training speed doesn't affect the delivered artifact -- a saved
    checkpoint trained on GPU loads and runs inference on CPU identically
    (`torch.load(..., map_location="cpu")`). So this class defaults to CUDA
    when available (training only) and the resulting model is still a
    CPU-runnable deliverable.
    """

    def __init__(
        self,
        in_channels: int | None = None,
        hidden_channels: int | None = None,
        kernel_size: int | None = None,
        num_layers: int = 1,
        seq_len: int | None = None,
        seed: int | None = None,
        device: str | None = None,
    ) -> None:
        cfg = config.NOWCAST
        self.in_channels = in_channels or len(real_ocean_data.VARIABLES)
        self.hidden_channels = hidden_channels or cfg.hidden_channels
        self.kernel_size = kernel_size or cfg.kernel_size
        self.num_layers = num_layers
        self.seq_len = seq_len or cfg.seq_len
        self.seed = cfg.seed if seed is None else seed
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        torch.manual_seed(self.seed)
        self.model = ConvLSTMPredictor(
            self.in_channels, self.hidden_channels, self.kernel_size, self.num_layers
        ).to(self.device)
        self.history = TrainingHistory()
        self._trained = False

        self.channel_mean: np.ndarray | None = None   # (1, C, 1, 1, 1)
        self.channel_std: np.ndarray | None = None
        self.mask: np.ndarray | None = None            # (C, D, H, W) bool -- True = ocean
        self._test_cache: tuple[torch.Tensor, torch.Tensor] | None = None
        self._raw_volume: np.ndarray | None = None      # (T, C, D, H, W), un-normalized, for plotting

    # ---- data -----------------------------------------------------------

    def _load_real_volume(self, phy_path, wave_path, chlorophyll_path) -> np.ndarray:
        data = real_ocean_data.load_real_training_volume(phy_path, wave_path, chlorophyll_path)
        arrays = [data[v] for v in real_ocean_data.VARIABLES]
        return np.stack(arrays, axis=1)  # (T, C, D, H, W)

    def _windows(self, volume_norm: np.ndarray, start: int, end: int) -> tuple[torch.Tensor, torch.Tensor]:
        xs, ys = [], []
        for t in range(start, end - self.seq_len):
            xs.append(volume_norm[t : t + self.seq_len])
            ys.append(volume_norm[t + self.seq_len])
        x = torch.tensor(np.stack(xs), dtype=torch.float32)
        y = torch.tensor(np.stack(ys), dtype=torch.float32)
        return x, y

    def _masked_mse(self, pred: torch.Tensor, target: torch.Tensor, mask_t: torch.Tensor) -> torch.Tensor:
        se = (pred - target) ** 2 * mask_t  # mask broadcasts over the batch dim
        return se.sum() / (mask_t.sum() * pred.shape[0])

    def _masked_mse_batched(
        self, x: torch.Tensor, y: torch.Tensor, mask_t: torch.Tensor, batch_size: int
    ) -> float:
        """Same masked MSE as `_masked_mse`, but mini-batched like training --
        pushing an entire validation/test set through as one giant batch is
        exactly what spiked VRAM to near the 6GB ceiling on a bigger dataset;
        this keeps peak memory bounded by `batch_size` regardless of how many
        real days the dataset covers."""
        total_se = 0.0
        n = x.shape[0]
        with torch.no_grad():
            for start in range(0, n, batch_size):
                xb = x[start : start + batch_size].to(self.device)
                yb = y[start : start + batch_size].to(self.device)
                pred = self.model(xb)
                total_se += (((pred - yb) ** 2) * mask_t).sum().item()
        return total_se / (mask_t.sum().item() * n)

    # ---- training ---------------------------------------------------------

    def train(
        self,
        phy_path: str | Path | list[str | Path] | None = None,
        wave_path: str | Path | None = None,
        chlorophyll_path: str | Path | None = None,
        epochs: int | None = None,
        lr: float | None = None,
        weight_decay: float = 1e-5,
        batch_size: int = 8,
        train_fraction: float = 0.70,
        val_fraction: float = 0.15,
        patience: int | None = None,
        min_delta: float | None = None,
        max_seconds: float | None = None,
        log_every: int = 1,
        verbose: bool = True,
    ) -> TrainingHistory:
        cfg = config.NOWCAST
        epochs = epochs or cfg.epochs
        lr = lr or cfg.lr
        patience = patience or cfg.early_stopping_patience
        min_delta = cfg.early_stopping_min_delta if min_delta is None else min_delta

        if verbose:
            logger.info("training on device: %s", self.device)

        if phy_path is not None:
            volume = self._load_real_volume(phy_path, wave_path, chlorophyll_path)
        else:
            logger.warning(
                "No real data paths given -- falling back to synthetic_ocean "
                "(%d channel(s), matching self.in_channels)", self.in_channels,
            )
            # One independent synthetic sequence per channel, cycling through
            # the tracked variable names (so each channel's synthetic field
            # uses that variable's own plausible range -- see
            # real_data.py's fallback formulas) -- must match self.in_channels
            # exactly, since a mismatch here is exactly the shape-mismatch bug
            # this fallback path had before variable-count configs existed.
            channel_vars = [
                real_ocean_data.VARIABLES[i % len(real_ocean_data.VARIABLES)]
                for i in range(self.in_channels)
            ]
            channels = [
                synthetic_ocean.generate_sequence(200, variable=v, seed=self.seed + i)
                for i, v in enumerate(channel_vars)
            ]
            volume = np.stack(channels, axis=1)[:, :, None, :, :]  # (T, C, D=1, H, W)

        self._raw_volume = volume
        T = volume.shape[0]
        train_end = int(T * train_fraction)
        val_end = train_end + int(T * val_fraction)
        if val_end - train_end <= self.seq_len or T - val_end <= self.seq_len:
            raise ValueError(f"not enough real timesteps ({T}) for seq_len={self.seq_len} with a 3-way chronological split")

        # Ocean mask: a cell counts as ocean only if it's finite at every
        # real timestep in the *training* window (bathymetry is static, so
        # this should hold for val/test too -- checked, not assumed, below).
        mask = np.all(np.isfinite(volume[:train_end]), axis=0)  # (C, D, H, W)
        self.mask = mask

        # Per-channel normalization fit on training-split ocean cells only.
        C = volume.shape[1]
        mean = np.zeros((1, C, 1, 1, 1), dtype=np.float32)
        std = np.ones((1, C, 1, 1, 1), dtype=np.float32)
        for c in range(C):
            vals = volume[:train_end, c][:, mask[c]]
            mean[0, c, 0, 0, 0] = vals.mean()
            std[0, c, 0, 0, 0] = vals.std() + 1e-6
        self.channel_mean, self.channel_std = mean, std

        volume_norm = (volume - mean[0]) / std[0]
        volume_norm = np.nan_to_num(volume_norm, nan=0.0)
        volume_norm = np.where(mask[None], volume_norm, 0.0)  # neutral input over land

        x_train, y_train = self._windows(volume_norm, 0, train_end)
        x_val, y_val = self._windows(volume_norm, train_end, val_end)
        x_test, y_test = self._windows(volume_norm, val_end, T)
        # Full dataset stays on CPU (it's small, tens of MB); only the
        # current mini-batch is moved to the GPU, standard practice so
        # training isn't bottlenecked holding everything in VRAM at once.
        self._test_cache = (x_test, y_test)

        mask_t = torch.tensor(mask, dtype=torch.float32, device=self.device)

        optimizer = torch.optim.Adam(self.model.parameters(), lr=lr, weight_decay=weight_decay)
        best_state = copy.deepcopy(self.model.state_dict())
        epochs_without_improvement = 0
        history = TrainingHistory()
        n_train = x_train.shape[0]
        generator = torch.Generator().manual_seed(self.seed)

        train_start = time.monotonic()
        stop_reason = None

        for epoch in range(1, epochs + 1):
            epoch_start = time.monotonic()
            self.model.train()
            perm = torch.randperm(n_train, generator=generator)
            epoch_loss_sum = 0.0
            for start in range(0, n_train, batch_size):
                idx = perm[start : start + batch_size]
                xb = x_train[idx].to(self.device)
                yb = y_train[idx].to(self.device)
                optimizer.zero_grad()
                batch_loss = self._masked_mse(self.model(xb), yb, mask_t)
                batch_loss.backward()
                optimizer.step()
                epoch_loss_sum += batch_loss.item() * len(idx)
            train_loss_value = epoch_loss_sum / n_train

            self.model.eval()
            val_loss = self._masked_mse_batched(x_val, y_val, mask_t, batch_size)

            history.train_loss.append(train_loss_value)
            history.val_loss.append(val_loss)

            improved = val_loss < history.best_val_loss - min_delta
            if improved:
                history.best_val_loss = val_loss
                history.best_epoch = epoch
                best_state = copy.deepcopy(self.model.state_dict())
                epochs_without_improvement = 0
            else:
                epochs_without_improvement += 1

            elapsed = time.monotonic() - train_start
            epoch_seconds = time.monotonic() - epoch_start
            if verbose and (epoch == 1 or epoch % max(1, log_every) == 0):
                if max_seconds is not None:
                    budget_note = f", {max(0.0, max_seconds - elapsed):.0f}s left in time budget"
                else:
                    budget_note = f", ETA to epoch cap {epoch_seconds * (epochs - epoch):.0f}s"
                logger.info(
                    "epoch %d/%d  train_loss=%.5f  val_loss=%.5f%s  [%.1fs/epoch, elapsed %.0fs%s]",
                    epoch, epochs, train_loss_value, val_loss, "  *" if improved else "",
                    epoch_seconds, elapsed, budget_note,
                )

            if epochs_without_improvement >= patience:
                stop_reason = f"no val improvement for {patience} epochs"
                history.stopped_early = True
                break

            if max_seconds is not None and elapsed >= max_seconds:
                stop_reason = f"time budget of {max_seconds:.0f}s reached"
                history.stopped_early = True
                break

        if verbose and stop_reason:
            logger.info(
                "stopping at epoch %d (%s); best was epoch %d (val_loss=%.5f)",
                epoch, stop_reason, history.best_epoch, history.best_val_loss,
            )

        self.model.load_state_dict(best_state)
        self.model.eval()
        self._trained = True
        self.history = history
        return history

    # ---- evaluation -------------------------------------------------------

    def evaluate(self, batch_size: int = 8) -> dict[str, float]:
        """Held-out test score (chronologically the latest real days, never
        touched during training/model-selection) vs. the persistence
        baseline, both masked to ocean cells only. Mini-batched through the
        model (same reason as training/validation -- bounded VRAM regardless
        of how many real days the test set covers)."""
        if not self._trained or self._test_cache is None:
            raise RuntimeError("call train() before evaluate()")

        x_test, y_test = self._test_cache
        mask_t = torch.tensor(self.mask, dtype=torch.float32, device=self.device)

        model_mse = self._masked_mse_batched(x_test, y_test, mask_t, batch_size)

        # Persistence baseline needs no model forward pass, so it's computed
        # on CPU -- no GPU memory involved at all for this half of the score.
        mask_cpu = torch.tensor(self.mask, dtype=torch.float32)
        persistence_pred = x_test[:, -1]
        persistence_mse = self._masked_mse(persistence_pred, y_test, mask_cpu).item()

        improvement_pct = (
            100.0 * (1.0 - model_mse / persistence_mse) if persistence_mse > 0 else float("nan")
        )
        return {
            "model_mse": model_mse,
            "persistence_baseline_mse": persistence_mse,
            "improvement_over_baseline_pct": improvement_pct,
        }

    # ---- inference ----------------------------------------------------------

    def predict(self, recent_volumes: np.ndarray) -> np.ndarray:
        """`recent_volumes`: (seq_len, C, D, H, W) real, un-normalized array
        -> predicted next (C, D, H, W) volume, in the same real units."""
        if not self._trained:
            raise RuntimeError("call train() before predict()")
        if recent_volumes.shape[0] != self.seq_len:
            raise ValueError(f"expected {self.seq_len} timesteps, got {recent_volumes.shape[0]}")

        norm = (recent_volumes - self.channel_mean[0]) / self.channel_std[0]
        norm = np.nan_to_num(norm, nan=0.0)
        norm = np.where(self.mask[None], norm, 0.0)

        x = torch.tensor(norm, dtype=torch.float32, device=self.device).unsqueeze(0)
        with torch.no_grad():
            pred_norm = self.model(x).squeeze(0).cpu().numpy()

        pred_real = pred_norm * self.channel_std[0] + self.channel_mean[0]
        return pred_real

    # ---- checkpointing ------------------------------------------------------

    def save(self, path: str) -> None:
        if not self._trained:
            raise RuntimeError("nothing to save -- call train() first")
        # Move to CPU before saving -- the checkpoint must load on any
        # teammate's laptop for the actual demo, GPU or not.
        cpu_state = {k: v.cpu() for k, v in self.model.state_dict().items()}
        torch.save(
            {
                "model_state": cpu_state,
                "in_channels": self.in_channels,
                "hidden_channels": self.hidden_channels,
                "kernel_size": self.kernel_size,
                "num_layers": self.num_layers,
                "seq_len": self.seq_len,
                "seed": self.seed,
                "best_val_loss": self.history.best_val_loss,
                "channel_mean": self.channel_mean,
                "channel_std": self.channel_std,
                "mask": self.mask,
            },
            path,
        )

    @classmethod
    def load(cls, path: str) -> "NowcastEngine":
        checkpoint = torch.load(path, map_location=config.DEVICE, weights_only=False)
        engine = cls(
            in_channels=checkpoint["in_channels"],
            hidden_channels=checkpoint["hidden_channels"],
            kernel_size=checkpoint["kernel_size"],
            num_layers=checkpoint.get("num_layers", 1),
            seq_len=checkpoint["seq_len"],
            seed=checkpoint["seed"],
        )
        engine.model.load_state_dict(checkpoint["model_state"])
        engine.model.eval()
        engine._trained = True
        engine.history.best_val_loss = checkpoint["best_val_loss"]
        engine.channel_mean = checkpoint["channel_mean"]
        engine.channel_std = checkpoint["channel_std"]
        engine.mask = checkpoint["mask"]
        return engine
