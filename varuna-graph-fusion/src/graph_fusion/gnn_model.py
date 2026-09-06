"""
The GNN architecture that powers the primary (non-fallback) fusion path.

A small multi-layer GCN (Kipf & Welling, 2017) operating in a semi-supervised
node-regression setting: sensor nodes are labelled with a known target (their
model-vs-observation residual), grid nodes are unlabelled, and the network
learns to propagate the residual signal across the connectivity-weighted
graph to predict a correction everywhere -- including at grid nodes that have
no sensor nearby in a straight-line sense but are well connected via the
current field.

GCNConv is used specifically because it accepts `edge_weight` directly in
message passing, so the oceanographic connectivity weights computed in
distance.py are not just used to decide *which* edges exist -- they directly
scale how much influence one node's signal has on another during training and
inference.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GCNConv


class GraphFusionGNN(nn.Module):
    def __init__(
        self,
        in_channels: int,
        hidden_channels: int,
        num_layers: int,
        out_channels: int,
        dropout: float,
    ):
        super().__init__()
        if num_layers < 2:
            raise ValueError("GraphFusionGNN needs at least 2 layers")

        self.convs = nn.ModuleList()
        self.convs.append(GCNConv(in_channels, hidden_channels))
        for _ in range(num_layers - 2):
            self.convs.append(GCNConv(hidden_channels, hidden_channels))
        self.convs.append(GCNConv(hidden_channels, hidden_channels))

        self.head = nn.Linear(hidden_channels, out_channels)
        self.dropout = dropout

    def forward(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
        edge_weight: torch.Tensor | None = None,
    ) -> torch.Tensor:
        h = x
        for conv in self.convs:
            h = conv(h, edge_index, edge_weight)
            h = F.relu(h)
            h = F.dropout(h, p=self.dropout, training=self.training)
        return self.head(h)
