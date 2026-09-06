"""
Drift Memory Service.

Coordinates memory state, detection algorithms, scenario simulations,
and optional upstream live data polling.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from .config import settings
from .detector import DriftDetector
from .memory import RegionalDriftMemory
from .mock_data import generate_mock_model, generate_mock_observations
from .scenarios import AnomalyScenario, apply_scenario
from .schemas import (
    Alert,
    FusedResponse,
    MemorySnapshotResponse,
    ModelSnapshot,
    ObservationSnapshot,
)

logger = logging.getLogger("drift_memory.service")


class DriftMemoryService:
    def __init__(
        self,
        memory: RegionalDriftMemory | None = None,
        detector: DriftDetector | None = None,
    ) -> None:
        self.memory = memory or RegionalDriftMemory()
        self.detector = detector or DriftDetector(memory=self.memory)
        self.current_scenario: AnomalyScenario = AnomalyScenario.MARINE_HEATWAVE

    def set_scenario(self, scenario: AnomalyScenario) -> None:
        """Switch current simulation scenario and clear debounce cache."""
        self.current_scenario = scenario
        self.detector.clear_debounce_cache()

    def get_alerts(self, scenario: Optional[AnomalyScenario] = None) -> list[Alert]:
        """
        Generate alerts under the specified (or default active) scenario
        using paired model and observation snapshots.
        """
        active_scn = scenario or self.current_scenario
        model, obs = apply_scenario(active_scn)
        return self.detector.evaluate_model_and_observations(model, obs)

    def evaluate_fused(self, fused: FusedResponse) -> list[Alert]:
        """Evaluate alerts directly from Person 1's /fused response."""
        return self.detector.evaluate_fused_response(fused)

    def evaluate_raw(
        self, model: ModelSnapshot, obs: ObservationSnapshot
    ) -> list[Alert]:
        """Evaluate alerts from arbitrary model and observation snapshots."""
        return self.detector.evaluate_model_and_observations(model, obs)

    async def fetch_upstream_fused_and_evaluate(self) -> list[Alert]:
        """
        Day 3 Upstream Integration:
        Query Person 1's Graph Fusion API (/fused) and evaluate live drift alerts.
        Falls back to scenario evaluation if upstream is unavailable.
        """
        url = f"{settings.graph_fusion_url}/fused"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                fused_data = FusedResponse.model_validate(resp.json())
                return self.evaluate_fused(fused_data)
        except Exception as exc:
            logger.warning("Upstream /fused unavailable (%s); falling back to scenario alerts", exc)
            return self.get_alerts()

    def get_memory_snapshot(self) -> MemorySnapshotResponse:
        """Inspect the internal test-time memory state across all sub-basins."""
        states = self.memory.get_all_states()
        alerts = self.get_alerts()
        return MemorySnapshotResponse(
            region=settings.region_name,
            memory_states=states,
            total_active_alerts=len(alerts),
            systematic_drift_detected=self.memory.has_systematic_drift(),
        )

    def reset(self) -> None:
        """Reset memory states and clear debounce cache."""
        self.memory.reset()
        self.detector.clear_debounce_cache()
