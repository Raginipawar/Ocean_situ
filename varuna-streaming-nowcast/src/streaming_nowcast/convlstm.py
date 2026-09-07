"""
ConvLSTM -- the Nowcast Engine's model (Section 10 of the work brief),
extended to a genuine 3D (depth x lat x lon) volume.

Same gated memory mechanism as the plain LSTM in streaming_backbone.py, but
every fully-connected operation is replaced with a convolution, so the state
itself is a spatial volume rather than a flat vector, and the gates learn
spatial filters instead of simple weighted sums. This is the Shi et al.
(2015) precipitation-nowcasting lineage the work brief specifies -- not the
JEPA-based version from the original draft (Section 10 explains why: no
ready-made library for ocean grids, higher build risk in the time
available).

Volumetric, not flat-surface: the team's own real Copernicus data comes with
real depth levels, and the frontend's 3D visualization is meant to show
depth structure, so the Nowcast Engine predicts a real (depth, lat, lon)
volume evolving over time -- `nn.Conv3d` in place of `nn.Conv2d`, same gate
logic otherwise.

CPU-only, stock `nn.Conv3d` only -- no compiled/custom CUDA kernels, so this
runs identically on any teammate's machine (Section 11's constraint applies
here exactly as it does to the streaming backbone).
"""
from __future__ import annotations

import torch
from torch import nn


class ConvLSTMCell(nn.Module):
    """One ConvLSTM step: (x_t, h_prev, c_prev) -> (h_t, c_t), over a
    (depth, height, width) volume.

    Mirrors streaming_backbone.lstm_state_update's gate logic exactly --
    forget/input/output gates over a running cell state -- but every gate is
    a learned 3D convolution over the concatenated [x_t, h_prev] volumes
    instead of a matrix multiply over a flat vector.
    """

    def __init__(self, in_channels: int, hidden_channels: int, kernel_size: int = 3) -> None:
        super().__init__()
        self.hidden_channels = hidden_channels
        padding = kernel_size // 2
        self.conv = nn.Conv3d(
            in_channels + hidden_channels,
            4 * hidden_channels,
            kernel_size=kernel_size,
            padding=padding,
        )

    def forward(
        self, x: torch.Tensor, h_prev: torch.Tensor, c_prev: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        combined = torch.cat([x, h_prev], dim=1)          # (B, Cin + Ch, D, H, W)
        gates = self.conv(combined)                        # (B, 4*Ch, D, H, W)
        i, f, g, o = gates.chunk(4, dim=1)
        i, f, o = torch.sigmoid(i), torch.sigmoid(f), torch.sigmoid(o)
        g = torch.tanh(g)
        c = f * c_prev + i * g
        h = o * torch.tanh(c)
        return h, c

    def init_state(
        self, batch_size: int, depth: int, height: int, width: int, device: torch.device | str
    ) -> tuple[torch.Tensor, torch.Tensor]:
        shape = (batch_size, self.hidden_channels, depth, height, width)
        return torch.zeros(shape, device=device), torch.zeros(shape, device=device)


class ConvLSTMPredictor(nn.Module):
    """Rolls a *stack* of ConvLSTMCells over an input sequence of volumes
    (each layer's hidden state feeds the next, same as Shi et al. 2015's own
    stacked-layer design -- one cell is the minimum working version, more
    layers is the literature's standard way to add capacity, not a
    departure from it), then reads the final layer's hidden state back out
    as a predicted *change* from the last observed volume via a 1x1x1
    convolution (a per-voxel linear projection from hidden channels to the
    tracked variable(s)).

    Predicting a residual rather than the raw next volume matters in
    practice, not just in theory: ocean fields like SST sit at a large,
    near-constant absolute value that barely moves between consecutive
    frames, so "predict nothing changes" (persistence) is already a strong
    baseline. A freshly-initialized conv net outputs values near zero, so if
    it had to predict the *raw* next volume from scratch it would start off
    enormously wrong and spend most of training just learning the absolute
    offset instead of the actual temporal dynamics. Adding the last volume
    back as a residual means the model starts at persistence-level accuracy
    for free, and gradient descent only has to learn the small correction on
    top -- standard practice in nowcasting/video-prediction models, and the
    more physically honest framing: "how is the state about to change", not
    "what is the state, from nothing".
    """

    def __init__(self, in_channels: int, hidden_channels: int, kernel_size: int = 3, num_layers: int = 1) -> None:
        super().__init__()
        self.num_layers = num_layers
        self.cells = nn.ModuleList(
            ConvLSTMCell(in_channels if i == 0 else hidden_channels, hidden_channels, kernel_size)
            for i in range(num_layers)
        )
        self.readout = nn.Conv3d(hidden_channels, in_channels, kernel_size=1)

    def forward(self, sequence: torch.Tensor) -> torch.Tensor:
        """sequence: (batch, time, channels, depth, height, width) ->
        predicted next volume (batch, channels, depth, height, width)."""
        batch, steps, _, depth, height, width = sequence.shape
        states = [cell.init_state(batch, depth, height, width, sequence.device) for cell in self.cells]

        for t in range(steps):
            layer_input = sequence[:, t]
            for i, cell in enumerate(self.cells):
                h, c = cell(layer_input, *states[i])
                states[i] = (h, c)
                layer_input = h  # this layer's hidden state feeds the next

        final_hidden = states[-1][0]
        delta = self.readout(final_hidden)
        return sequence[:, -1] + delta
