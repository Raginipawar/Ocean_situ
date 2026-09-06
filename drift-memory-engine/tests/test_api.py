"""Integration tests for Drift Memory API."""
import pytest
from fastapi.testclient import TestClient

from drift_memory.api import app, service
from drift_memory.scenarios import AnomalyScenario


@pytest.fixture
def client():
    service.reset()
    return TestClient(app)


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "drift_memory_engine"
    assert "north_bob" in data["sub_basins"]


def test_alerts_endpoint(client):
    resp = client.get("/alerts")
    assert resp.status_code == 200
    alerts = resp.json()
    assert isinstance(alerts, list)
    assert len(alerts) > 0
    first = alerts[0]
    assert "id" in first
    assert "severity" in first
    assert "message" in first
    assert "divergence" in first


def test_scenario_switching(client):
    resp = client.post(f"/scenario/{AnomalyScenario.NOMINAL.value}")
    assert resp.status_code == 200
    assert resp.json()["scenario"] == "nominal"

    # Reset cache and get nominal alerts
    alerts_resp = client.get("/alerts")
    assert alerts_resp.status_code == 200
    nominal_alerts = alerts_resp.json()
    assert not any(a["severity"] == "critical" for a in nominal_alerts)


def test_memory_state_endpoint(client):
    # Fire an alert evaluation first
    client.get("/alerts?scenario=marine_heatwave")
    resp = client.get("/memory/state")
    assert resp.status_code == 200
    data = resp.json()
    assert data["region"] == "bay_of_bengal"
    assert "memory_states" in data
    assert isinstance(data["memory_states"], list)
