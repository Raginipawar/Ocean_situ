"""Unit tests for Titans-inspired Test-Time Memory module."""
from datetime import datetime, timezone
import pytest

from drift_memory.memory import MemoryCell, RegionalDriftMemory
from drift_memory.schemas import AlertSeverity


def test_memory_cell_initial_state():
    cell = MemoryCell(sub_basin="central_bob", variable="sst")
    assert cell.observation_count == 0
    assert cell.rolling_drift == 0.0
    assert cell.rolling_surprise == 0.0
    assert not cell.is_anomalous
    assert cell.active_severity == AlertSeverity.info


def test_memory_cell_update_adaptation():
    cell = MemoryCell(sub_basin="central_bob", variable="sst")
    
    # First nominal update
    cell.update(signed_error=0.2, normalized_surprise=0.4)
    assert cell.observation_count == 1
    assert cell.rolling_drift == 0.2
    assert cell.rolling_surprise == 0.4
    assert not cell.is_anomalous

    # Large surprise update (Titans-style shock)
    cell.update(signed_error=2.4, normalized_surprise=4.8)
    assert cell.observation_count == 2
    # Alpha boosted due to surprise >= 2.5
    assert cell.rolling_surprise > 1.5
    assert len(cell.history) == 2


def test_regional_drift_memory_matrix():
    memory = RegionalDriftMemory()
    cell1 = memory.get_cell("north_bob", "sst")
    cell2 = memory.get_cell("north_bob", "currents")
    cell3 = memory.get_cell("central_bob", "sst")

    assert cell1 != cell2
    assert cell1 != cell3

    # Record persistent extreme divergence
    for _ in range(5):
        memory.record_update("north_bob", "sst", signed_error=2.5, normalized_surprise=5.0)

    states = memory.get_all_states()
    assert len(states) == 3
    assert memory.has_systematic_drift()

    # Reset
    memory.reset()
    assert len(memory.get_all_states()) == 0
    assert not memory.has_systematic_drift()
