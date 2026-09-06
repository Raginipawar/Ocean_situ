"""
Orchestrates one end-to-end fusion pass:

    /model + /observations -> sanitize -> graph -> engine (GNN,
    auto-falling-back to the graph-weighted engine) -> trust overlay -> /fused

This is the single entry point the API layer (api.py) and the CLI demo
(scripts/run_demo.py) both call, so there is exactly one place that encodes
"never cut the core loop": if the GNN engine fails for *any* reason, this
service silently and automatically drops to the fallback engine rather than
raising, unless the caller explicitly pinned `engine="gnn"`.

Two more things live here, both aimed at Day 3 (wiring in real, occasionally
messy data) rather than the current mock path:

- **Sanitization** (`sanitize.py`) runs before the graph is built, so QC
  fill values and out-of-range readings from a flaky real sensor read as
  missing rather than as data that skews the correction.
- **Content-keyed caching**: identical (model, obs, variables, engine) input
  returns the cached result instead of retraining the GNN from scratch
  (~2-3s). Keyed on actual values, not timestamps, so it never serves stale
  results once real streaming data is involved -- a genuinely new reading
  changes the hash and triggers real recomputation.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from collections import OrderedDict

import numpy as np

from . import config
from .fallback_engine import FallbackFusionEngine
from .gnn_engine import GNNFusionEngine
from .graph_builder import SensorGraphBuilder
from .sanitize import sanitize_model, sanitize_observations
from .schemas import FusedPoint, FusedResponse, FusionSummary, ModelSnapshot, ObservationSnapshot
from .trust_overlay import compute_trust

logger = logging.getLogger("graph_fusion")


class FusionService:
    def __init__(
        self,
        graph_builder: SensorGraphBuilder | None = None,
        gnn_engine: GNNFusionEngine | None = None,
        fallback_engine: FallbackFusionEngine | None = None,
        cache_size: int = 16,
    ):
        self.builder = graph_builder or SensorGraphBuilder()
        self.gnn_engine = gnn_engine or GNNFusionEngine()
        self.fallback_engine = fallback_engine or FallbackFusionEngine()
        # Content-keyed, not time-keyed: real streaming data changes the hash
        # the moment a new reading actually arrives, so this never serves
        # stale results -- it only skips redundant retraining (the GNN
        # currently retrains from scratch every call, ~2-3s) when nothing
        # about the input actually changed, e.g. a frontend "refresh" click
        # against the same underlying snapshot.
        self._cache: OrderedDict[str, FusedResponse] = OrderedDict()
        self._cache_size = cache_size

    @staticmethod
    def _cache_key(
        model: ModelSnapshot, obs: ObservationSnapshot, variables: list[str], engine: str
    ) -> str:
        payload = {
            "engine": engine,
            "variables": variables,
            "region": model.region,
            "model_points": [
                [p.lat, p.lon, p.depth_m] + [getattr(p, v) for v in variables] for p in model.points
            ],
            "obs_points": [
                [p.sensor_id, p.lat, p.lon, p.depth_m] + [getattr(p, v) for v in variables]
                for p in obs.points
            ],
        }
        blob = json.dumps(payload, sort_keys=True, default=str).encode()
        return hashlib.sha256(blob).hexdigest()

    def fuse(
        self,
        model: ModelSnapshot,
        obs: ObservationSnapshot,
        variables: list[str] | None = None,
        engine: str = "auto",
    ) -> FusedResponse:
        if engine not in ("auto", "gnn", "fallback"):
            raise ValueError(f"Unknown engine '{engine}'; expected auto|gnn|fallback")

        start = time.perf_counter()
        variables = variables or config.VARIABLES

        model, _ = sanitize_model(model)
        obs, _ = sanitize_observations(obs)

        cache_key = self._cache_key(model, obs, variables, engine)
        cached = self._cache.get(cache_key)
        if cached is not None:
            self._cache.move_to_end(cache_key)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            return cached.model_copy(
                update={"summary": cached.summary.model_copy(update={"runtime_ms": elapsed_ms})}
            )

        fg = self.builder.build(model, obs, variables)

        corrections: np.ndarray | None = None
        engine_used: str | None = None
        validation_mae_sst: float | None = None

        if engine in ("auto", "gnn"):
            try:
                corrections, diag = self.gnn_engine.fit_predict(fg)
                engine_used = "gnn"
                validation_mae_sst = diag.val_mae.get("sst_c")
            except Exception as exc:  # noqa: BLE001 - deliberate: any GNN failure degrades gracefully
                if engine == "gnn":
                    raise
                logger.warning(
                    "GNN fusion engine unavailable (%s); falling back to graph-weighted correction.",
                    exc,
                )

        if corrections is None:
            corrections, _fallback_diag = self.fallback_engine.predict(fg)
            engine_used = "fallback"

        confidence, labels, support = compute_trust(fg, corrections, variables)

        points: list[FusedPoint] = []
        for i, node_id in enumerate(fg.node_ids):
            kwargs: dict = dict(
                lat=float(fg.lat[i]),
                lon=float(fg.lon[i]),
                depth_m=float(fg.depth_m[i]),
                confidence=float(confidence[i]),
                trust_label=labels[i],
                is_sensor_node=bool(fg.is_sensor[i]),
                support=float(support[i]),
            )
            for vi, var in enumerate(variables):
                background_val = fg.background[var][i]
                if np.isnan(background_val):
                    kwargs[var] = None
                    kwargs[f"correction_{var}"] = None
                else:
                    correction = float(corrections[i, vi])
                    kwargs[var] = float(background_val + correction)
                    kwargs[f"correction_{var}"] = correction
            points.append(FusedPoint(**kwargs))

        runtime_ms = (time.perf_counter() - start) * 1000.0
        primary_idx = variables.index("sst_c") if "sst_c" in variables else 0
        primary_corrections = corrections[:, primary_idx]

        summary = FusionSummary(
            engine=engine_used,  # type: ignore[arg-type]
            n_sensors=fg.n_sensors,
            n_grid_points=fg.n_grid_points,
            n_graph_edges=fg.nx_graph.number_of_edges(),
            mean_confidence=float(np.mean(confidence)) if len(confidence) else 0.0,
            mean_abs_correction_sst_c=float(np.mean(np.abs(primary_corrections))) if len(primary_corrections) else None,
            validation_mae_sst_c=validation_mae_sst,
            runtime_ms=runtime_ms,
        )

        result = FusedResponse(region=model.region, time=model.time, points=points, summary=summary)

        self._cache[cache_key] = result
        self._cache.move_to_end(cache_key)
        if len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)

        return result
