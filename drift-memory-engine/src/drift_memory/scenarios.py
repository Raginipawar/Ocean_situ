"""
Scenario Injectors for Demo and Validation.

Allows injecting realistic oceanographic divergence scenarios:
- Nominal: Forecast matches ground truth within typical error bounds (< 0.4°C).
- Marine Heatwave (MHW): Extreme +2.2°C SST surge in Central/North Bay of Bengal.
- Boundary Current Shear: East India Coastal Current (EICC) direction reversal.
- Compound Anomaly: Multi-variable divergence across SST, currents, and waves.
"""
from __future__ import annotations

from enum import Enum
from .mock_data import generate_mock_model, generate_mock_observations
from .schemas import ModelSnapshot, ObservationSnapshot


class AnomalyScenario(str, Enum):
    NOMINAL = "nominal"
    MARINE_HEATWAVE = "marine_heatwave"
    BOUNDARY_CURRENT_SHEAR = "boundary_current_shear"
    COMPOUND_ANOMALY = "compound_anomaly"


def apply_scenario(
    scenario: AnomalyScenario,
    model: ModelSnapshot | None = None,
    obs: ObservationSnapshot | None = None,
) -> tuple[ModelSnapshot, ObservationSnapshot]:
    """
    Take baseline model and observation snapshots and inject the chosen scenario.
    """
    m = model or generate_mock_model()
    o = obs or generate_mock_observations()

    if scenario == AnomalyScenario.NOMINAL:
        return m, o

    if scenario in (AnomalyScenario.MARINE_HEATWAVE, AnomalyScenario.COMPOUND_ANOMALY):
        # Inject +2.3°C SST anomaly into observations located in Central/North BoB (lat > 14.0)
        for pt in o.points:
            if pt.lat >= 14.0 and pt.sst_c is not None:
                pt.sst_c += 2.35

    if scenario in (AnomalyScenario.BOUNDARY_CURRENT_SHEAR, AnomalyScenario.COMPOUND_ANOMALY):
        # Inject strong current shear along East Coast (lon < 84.0)
        for pt in o.points:
            if pt.lon <= 84.0:
                # Reverse and intensify current vectors
                pt.current_u_ms = 0.55
                pt.current_v_ms = -0.70

    if scenario == AnomalyScenario.COMPOUND_ANOMALY:
        # Also inject wave height underprediction
        for pt in o.points:
            if pt.wave_height_m is not None:
                pt.wave_height_m += 1.80

    return m, o
