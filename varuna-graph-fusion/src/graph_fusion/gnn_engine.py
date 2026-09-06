"""
Training/inference driver for the GNN fusion path.

Validation strategy -- "how do you know this generalises to the grid if you
have no ground truth there?": we hold out a random subset of *sensors* from
the training loss (their node features are still visible to the graph, only
their labels are hidden) and report the mean absolute error of the model's
predicted correction against their real, known residual. This is the same
transductive semi-supervised evaluation regime used in the original GCN node
classification/regression literature, and it is the closest honest proxy we
have for "would this correction be trustworthy at an unobserved grid point".
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import torch
import torch.nn.functional as F

from . import config
from .gnn_model import GraphFusionGNN
from .graph_builder import FusionGraph


@dataclass
class GNNDiagnostics:
    val_mae: dict[str, float] = field(default_factory=dict)
    final_train_loss: float | None = None
    n_train_sensors: int = 0
    n_val_sensors: int = 0
    epochs_run: int = 0


class GNNFusionEngine:
    """Semi-supervised GCN over the sensor+grid connectivity graph."""

    name = "gnn"

    def __init__(self, gnn_config: config.GNNConfig = config.GNN):
        self.cfg = gnn_config

    def fit_predict(self, fg: FusionGraph) -> tuple[np.ndarray, GNNDiagnostics]:
        if fg.n_sensors < self.cfg.min_sensors_for_training:
            raise RuntimeError(
                f"Only {fg.n_sensors} sensor node(s); need at least "
                f"{self.cfg.min_sensors_for_training} to train the GNN safely."
            )
        if fg.edge_index.shape[1] == 0:
            raise RuntimeError("Fusion graph has no edges; cannot train a GNN over it.")

        torch.manual_seed(self.cfg.seed)
        rng = np.random.default_rng(self.cfg.seed)

        x = torch.tensor(fg.features, dtype=torch.float32)
        edge_index = torch.tensor(fg.edge_index, dtype=torch.long)
        edge_weight = torch.tensor(fg.edge_weight, dtype=torch.float32)

        n_vars = len(fg.variables)
        y = np.full((fg.n_nodes, n_vars), np.nan, dtype=np.float32)
        for vi, var in enumerate(fg.variables):
            y[:, vi] = fg.residual[var]
        y_t = torch.tensor(y, dtype=torch.float32)
        label_mask = ~torch.isnan(y_t)

        sensor_idx = fg.sensor_indices()
        perm = rng.permutation(sensor_idx)
        n_val = int(len(perm) * self.cfg.val_fraction)
        if len(perm) < 5:
            n_val = 0  # too few sensors to bother splitting; train on all of them
        val_idx = perm[:n_val]
        train_idx = perm[n_val:]

        train_mask = torch.zeros(fg.n_nodes, dtype=torch.bool)
        val_mask = torch.zeros(fg.n_nodes, dtype=torch.bool)
        train_mask[train_idx] = True
        if n_val > 0:
            val_mask[val_idx] = True

        model = GraphFusionGNN(
            in_channels=fg.features.shape[1],
            hidden_channels=self.cfg.hidden_channels,
            num_layers=self.cfg.num_layers,
            out_channels=n_vars,
            dropout=self.cfg.dropout,
        )
        optimizer = torch.optim.Adam(
            model.parameters(), lr=self.cfg.lr, weight_decay=self.cfg.weight_decay
        )

        y_filled = torch.nan_to_num(y_t, nan=0.0)
        train_label_mask = label_mask & train_mask.unsqueeze(1)
        if train_label_mask.sum() == 0:
            raise RuntimeError("No labelled training targets available for the GNN.")

        final_loss = None
        model.train()
        for _ in range(self.cfg.epochs):
            optimizer.zero_grad()
            pred = model(x, edge_index, edge_weight)
            loss = F.mse_loss(pred[train_label_mask], y_filled[train_label_mask])
            loss.backward()
            optimizer.step()
            final_loss = float(loss.item())

        model.eval()
        with torch.no_grad():
            pred = model(x, edge_index, edge_weight)

        val_mae: dict[str, float] = {}
        for vi, var in enumerate(fg.variables):
            vmask = label_mask[:, vi] & val_mask
            if vmask.sum() > 0:
                mae = torch.mean(torch.abs(pred[vmask, vi] - y_filled[vmask, vi])).item()
                val_mae[var] = float(mae)

        diagnostics = GNNDiagnostics(
            val_mae=val_mae,
            final_train_loss=final_loss,
            n_train_sensors=int(train_mask.sum().item()),
            n_val_sensors=int(val_mask.sum().item()),
            epochs_run=self.cfg.epochs,
        )
        return pred.detach().numpy(), diagnostics
