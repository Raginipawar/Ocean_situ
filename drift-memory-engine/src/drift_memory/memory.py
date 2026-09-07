"""
Titans-inspired Test-Time Memory Architecture for Ocean Drift.

Rather than static point-in-time thresholding, this module maintains a rolling,
adaptive state of model-vs-reality divergence per ocean sub-basin and variable.
When a sustained bias emerges, the memory registers systematic model drift;
when an acute shock occurs (e.g. marine heatwave), the surprise signal surges.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Tuple
import numpy as np

from .config import settings
from .schemas import AlertSeverity, SubBasinMemoryState


class MemoryCell:
    """
    Test-time memory unit for a single (sub_basin, variable) pair.
    
    Maintains:
    - rolling_drift: signed rolling bias (e.g. +1.4°C indicates persistent warm bias)
    - rolling_surprise: non-negative surprise metric (normalized discrepancy)
    - observation_count: total observation updates received
    """

    def __init__(self, sub_basin: str, variable: str) -> None:
        self.sub_basin = sub_basin
        self.variable = variable
        self.rolling_drift: float = 0.0
        self.rolling_surprise: float = 0.0
        self.observation_count: int = 0
        self.last_updated: datetime = datetime.now(timezone.utc)
        self.history: list[float] = []

    def update(
        self,
        signed_error: float,
        normalized_surprise: float,
        timestamp: datetime | None = None,
    ) -> None:
        """
        Update memory state with new observation innovation.
        
        Uses adaptive momentum: if normalized surprise exceeds 2.5 sigma,
        the update rate increases (accelerated test-time adaptation).
        """
        alpha = settings.memory_momentum_alpha
        if normalized_surprise >= 2.5:
            # Accelerated adaptation to capture rapid regime shifts
            alpha = min(0.85, alpha * settings.adaptive_surprise_boost)

        if self.observation_count == 0:
            self.rolling_drift = signed_error
            self.rolling_surprise = normalized_surprise
        else:
            self.rolling_drift = (1.0 - alpha) * self.rolling_drift + alpha * signed_error
            self.rolling_surprise = (1.0 - alpha) * self.rolling_surprise + alpha * normalized_surprise

        self.observation_count += 1
        self.last_updated = timestamp or datetime.now(timezone.utc)
        self.history.append(normalized_surprise)
        if len(self.history) > 100:
            self.history.pop(0)

    @property
    def is_anomalous(self) -> bool:
        """Surprise score exceeds 2.0 standard deviations."""
        return self.rolling_surprise >= 2.0

    @property
    def active_severity(self) -> AlertSeverity:
        if self.rolling_surprise >= 3.5:
            return AlertSeverity.critical
        if self.rolling_surprise >= 2.0:
            return AlertSeverity.warning
        return AlertSeverity.info

    def to_schema(self) -> SubBasinMemoryState:
        return SubBasinMemoryState(
            sub_basin=self.sub_basin,
            variable=self.variable,
            rolling_drift=round(self.rolling_drift, 3),
            rolling_surprise=round(self.rolling_surprise, 3),
            observation_count=self.observation_count,
            last_updated=self.last_updated,
            active_severity=self.active_severity,
            is_anomalous=self.is_anomalous,
        )


class RegionalDriftMemory:
    """
    Maintains the global matrix of MemoryCells across all Bay of Bengal
    sub-basins and physical ocean variables.
    """

    def __init__(self) -> None:
        self._cells: Dict[Tuple[str, str], MemoryCell] = {}

    def get_cell(self, sub_basin: str, variable: str) -> MemoryCell:
        key = (sub_basin, variable)
        if key not in self._cells:
            self._cells[key] = MemoryCell(sub_basin=sub_basin, variable=variable)
        return self._cells[key]

    def record_update(
        self,
        sub_basin: str,
        variable: str,
        signed_error: float,
        normalized_surprise: float,
        timestamp: datetime | None = None,
    ) -> MemoryCell:
        cell = self.get_cell(sub_basin, variable)
        cell.update(signed_error, normalized_surprise, timestamp)
        return cell

    def get_all_states(self) -> list[SubBasinMemoryState]:
        return [cell.to_schema() for cell in self._cells.values()]

    def has_systematic_drift(self) -> bool:
        """Returns true if any sub-basin exhibits persistent high-severity drift."""
        return any(cell.active_severity == AlertSeverity.critical for cell in self._cells.values())

    def reset(self) -> None:
        """Clear memory cells (useful for scenario restarts)."""
        self._cells.clear()
