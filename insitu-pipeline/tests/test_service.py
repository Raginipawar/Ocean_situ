"""
Test FastAPI microservice endpoints.
"""
from fastapi.testclient import TestClient

from varuna_insitu_pipeline.service import app

client = TestClient(app)


def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "registered_adapters" in data


def test_adapters_endpoint():
    resp = client.get("/adapters")
    assert resp.status_code == 200
    data = resp.json()
    assert "local_demo" in data["registered_adapters"]


def test_observations_endpoint():
    resp = client.get("/observations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["region"] == "bay_of_bengal"
    assert "points" in data
    assert len(data["points"]) > 0

    first_point = data["points"][0]
    assert "sensor_id" in first_point
    assert "sensor_type" in first_point
    assert "lat" in first_point
    assert "lon" in first_point
    assert "sst_c" in first_point


def test_profiles_endpoint():
    resp = client.get("/profiles")
    assert resp.status_code == 200
    profiles = resp.json()
    assert isinstance(profiles, list)
    assert len(profiles) > 0
    assert "levels" in profiles[0]


def test_qc_report_endpoint():
    resp = client.get("/qc-report")
    assert resp.status_code == 200
    qc = resp.json()
    assert "retained_records" in qc
