"""Unit tests for Drift and Divergence Detector."""
from datetime import datetime, timezone
import pytest

from drift_memory.detector import DriftDetector
from drift_memory.mock_data import generate_mock_model, generate_mock_observations
from drift_memory.scenarios import AnomalyScenario, apply_scenario
from drift_memory.schemas import (
    AlertSeverity,
    FusedPoint,
    FusedResponse,
    FusionSummary,
)


def test_nominal_scenario_produces_few_or_no_critical_alerts():
    detector = DriftDetector()
    model, obs = apply_scenario(AnomalyScenario.NOMINAL)
    alerts = detector.evaluate_model_and_observations(model, obs)
    
    # Under nominal, there should be NO critical alerts
    critical_alerts = [a for a in alerts if a.severity == AlertSeverity.critical]
    assert len(critical_alerts) == 0


def test_marine_heatwave_triggers_critical_alert():
    detector = DriftDetector()
    model, obs = apply_scenario(AnomalyScenario.MARINE_HEATWAVE)
    alerts = detector.evaluate_model_and_observations(model, obs)

    # Should detect critical SST anomaly
    critical_sst = [
        a for a in alerts if a.variable == "sst" and a.severity == AlertSeverity.critical
    ]
    assert len(critical_sst) > 0
    first = critical_sst[0]
    assert first.divergence >= 2.0
    assert "Marine Heatwave" in first.message or "SST" in first.message


def test_fused_response_evaluation():
    detector = DriftDetector()
    now = datetime.now(timezone.utc)
    
    # Construct synthetic FusedResponse mimicking Person 1 output
    fused = FusedResponse(
        region="bay_of_bengal",
        time=now,
        points=[
            FusedPoint(
                lat=15.0,
                lon=88.0,
                depth_m=0.0,
                sst_c=28.5,
                correction_sst_c=2.2,     # Divergence of +2.2°C
                current_u_ms=0.2,
                current_v_ms=-0.1,
                correction_current_u_ms=0.5,
                correction_current_v_ms=-0.4,
                confidence=0.92,
                trust_label="red",
            )
        ],
        summary=FusionSummary(
            engine="gnn",
            n_sensors=1,
            n_grid_points=1,
            n_graph_edges=1,
            mean_confidence=0.92,
            runtime_ms=12.5,
        ),
    )

    alerts = detector.evaluate_fused_response(fused)
    assert len(alerts) >= 1
    sst_alerts = [a for a in alerts if a.variable == "sst"]
    assert len(sst_alerts) == 1
    assert sst_alerts[0].severity == AlertSeverity.critical


def test_alert_debouncing():
    detector = DriftDetector()
    model, obs = apply_scenario(AnomalyScenario.MARINE_HEATWAVE)

    # First evaluation generates alerts
    alerts1 = detector.evaluate_model_and_observations(model, obs)
    assert len(alerts1) > 0

    # Immediate second evaluation should debounce duplicate (sub_basin, variable) alerts
    alerts2 = detector.evaluate_model_and_observations(model, obs)
    assert len(alerts2) == 0

    # Clearing cache re-enables immediate alerting
    detector.clear_debounce_cache()
    alerts3 = detector.evaluate_model_and_observations(model, obs)
    assert len(alerts3) > 0
