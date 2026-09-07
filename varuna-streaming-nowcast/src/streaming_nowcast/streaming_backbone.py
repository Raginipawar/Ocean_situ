"""
Streaming Backbone -- the real-time ingestion state-update logic (Task 1.2,
Technical Deep Dive in Section 9 of the work brief).

Core idea: a standard LSTM cell maintains a cell state (long-term memory) and
a hidden state (short-term, output-facing memory). Because it only needs the
current input and the previous state to produce the next state, it never
needs to reprocess history from scratch -- this is exactly what "real-time
ingestion state-update logic" means in the project's language, and it's what
makes this a streaming, linear-time design rather than a batch one.

Deliberately NOT torch.nn.LSTM: this is a plain, from-scratch, ~20-line
tensor-op implementation so anyone on the team (or a judge) can read the
update rule line-by-line -- see Section 9's "why ~20 lines matters". CPU-only,
no compiled extensions -- see config.DEVICE and Section 11 (the Mamba/SSM
question): this is deliberately not Mamba/SSM, for the reasons documented
there.
"""
from __future__ import annotations

import math
from collections import deque

import torch

from . import config
from .schemas import StreamingState


def lstm_state_update(
    x: torch.Tensor,
    h_prev: torch.Tensor,
    c_prev: torch.Tensor,
    weight: torch.Tensor,
    bias: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """One streaming LSTM step: (input, prev hidden, prev cell) -> (new hidden, new cell).

    This is the whole state-update rule -- forget/input/output gates control
    what's discarded, what's added, and what's exposed from the running cell
    state. It depends on nothing but (x, h_prev, c_prev): the defining
    property of a linear-time streaming update, as opposed to reprocessing
    history from scratch on every new reading.
    """
    z = torch.cat([x, h_prev])                # input concatenated with prev hidden state
    gates = weight @ z + bias                 # (4 * hidden_dim,)
    i, f, g, o = gates.chunk(4)                # input, forget, candidate, output gates
    i, f, o = torch.sigmoid(i), torch.sigmoid(f), torch.sigmoid(o)
    g = torch.tanh(g)
    c = f * c_prev + i * g                    # forget old cell content, add new candidate
    h = o * torch.tanh(c)                     # expose part of the updated cell state
    return h, c


class StreamingBackbone:
    """Wraps `lstm_state_update` with persistent state and gap/burst handling.

    Feed it one reading at a time via `ingest()`, a missing timestep via
    `ingest(None)`, or several readings that arrived close together via
    `ingest_batch()` -- see Task 2.3 (stress-test gaps and bursts). The
    weights are fixed at construction (random, seeded): this component's job
    is demonstrating a stable, continuous, real-time *state update*, not
    learning -- there is nothing to train it against until a downstream task
    (e.g. Nowcast) defines a loss.
    """

    def __init__(
        self,
        input_dim: int | None = None,
        hidden_dim: int | None = None,
        seed: int | None = None,
    ) -> None:
        self.input_dim = input_dim or config.STREAMING.input_dim
        self.hidden_dim = hidden_dim or config.STREAMING.hidden_dim
        seed = config.STREAMING.seed if seed is None else seed

        generator = torch.Generator(device=config.DEVICE).manual_seed(seed)
        scale = 1.0 / math.sqrt(self.hidden_dim + self.input_dim)
        self.weight = (
            torch.rand(
                (4 * self.hidden_dim, self.hidden_dim + self.input_dim),
                generator=generator,
            )
            * 2
            - 1
        ) * scale
        self.bias = torch.zeros(4 * self.hidden_dim)

        self.h = torch.zeros(self.hidden_dim)
        self.c = torch.zeros(self.hidden_dim)
        self._last_input: list[float] | None = None
        self.step_count = 0
        self.history: deque[StreamingState] = deque(maxlen=config.STREAMING.history_maxlen)

    @staticmethod
    def _sanitize(reading: list[float] | None) -> torch.Tensor | None:
        """None -> a gap. Any None/NaN *field* inside a real reading (a
        sensor that doesn't report every variable) is treated as "no new
        information for that channel" rather than corrupting the whole
        update."""
        if reading is None:
            return None
        clean = [0.0 if (v is None or v != v) else float(v) for v in reading]
        return torch.tensor(clean, dtype=torch.float32)

    def ingest(self, reading: list[float] | None) -> StreamingState:
        """Process one reading. `reading=None` means a missing timestep (a
        gap) -- the state persists unchanged rather than crashing or
        hallucinating a fabricated zero reading."""
        x = self._sanitize(reading)
        was_gap = x is None
        if not was_gap:
            if x.shape[0] != self.input_dim:
                raise ValueError(f"expected a length-{self.input_dim} reading, got {x.shape[0]}")
            self.h, self.c = lstm_state_update(x, self.h, self.c, self.weight, self.bias)
            self._last_input = x.tolist()

        if not torch.isfinite(self.h).all() or not torch.isfinite(self.c).all():
            raise FloatingPointError(f"streaming state diverged to NaN/Inf at step {self.step_count + 1}")

        self.step_count += 1
        state = StreamingState(
            step=self.step_count,
            hidden_state=self.h.tolist(),
            cell_state=self.c.tolist(),
            last_input=self._last_input,
            was_gap=was_gap,
        )
        self.history.append(state)
        return state

    def ingest_batch(self, readings: list[list[float] | None]) -> list[StreamingState]:
        """Process a burst of several readings that arrived close together,
        in order, without blocking (Task 2.3)."""
        return [self.ingest(r) for r in readings]

    @property
    def state_vector(self) -> list[float]:
        """The current hidden state -- what a downstream consumer (e.g. the
        Nowcast Engine, or a future /streaming-state endpoint via Person 5)
        would read."""
        return self.h.tolist()
