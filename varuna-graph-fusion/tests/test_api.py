from fastapi.testclient import TestClient

from graph_fusion.api import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_model_endpoint():
    r = client.get("/model")
    assert r.status_code == 200
    body = r.json()
    assert len(body["points"]) > 0
    assert "sst_c" in body["points"][0]


def test_observations_endpoint():
    r = client.get("/observations")
    assert r.status_code == 200
    body = r.json()
    assert len(body["points"]) > 0
    assert "sensor_type" in body["points"][0]


def test_fused_endpoint_default_auto():
    r = client.get("/fused")
    assert r.status_code == 200
    body = r.json()
    assert body["summary"]["engine"] in ("gnn", "fallback")
    assert len(body["points"]) > 0
    assert 0.0 <= body["points"][0]["confidence"] <= 1.0


def test_fused_endpoint_forced_fallback_is_fast_and_deterministic_engine_choice():
    r = client.get("/fused", params={"engine": "fallback"})
    assert r.status_code == 200
    assert r.json()["summary"]["engine"] == "fallback"


def test_fused_endpoint_invalid_engine_rejected():
    r = client.get("/fused", params={"engine": "bogus"})
    assert r.status_code == 422
