"""
Test data schemas and compatibility with Person 1 (graph_fusion) contract.
"""
import json
from datetime import datetime, timezone

from varuna_insitu_pipeline.schemas import (
    ObservationPoint,
    ObservationSnapshot,
    RegionBounds,
    SensorType,
)


def test_observation_point_creation():
    point = ObservationPoint(
        sensor_id="argo-2903412",
        sensor_type=SensorType.ARGO,
        lat=13.05,
        lon=87.98,
        depth_m=0.0,
        time=datetime(2026, 9, 7, 10, 0, 0, tzinfo=timezone.utc),
        sst_c=30.1,
        current_u_ms=0.12,
        current_v_ms=-0.05,
        wave_height_m=1.2,
        salinity_psu=33.5,
        chlorophyll_mg_m3=0.35,
    )
    assert point.sensor_id == "argo-2903412"
    assert point.sensor_type == SensorType.ARGO
    assert point.lat == 13.05
    assert point.sst_c == 30.1
    assert point.salinity_psu == 33.5


def test_observation_snapshot_serialization():
    point = ObservationPoint(
        sensor_id="buoy-bd08",
        sensor_type=SensorType.BUOY,
        lat=18.2,
        lon=89.7,
        depth_m=0.0,
        time=datetime.now(timezone.utc),
        sst_c=29.4,
        wave_height_m=1.5,
    )
    snapshot = ObservationSnapshot(
        region="bay_of_bengal",
        time=datetime.now(timezone.utc),
        source="local_demo",
        points=[point],
    )

    data = snapshot.model_dump(mode="json")
    assert data["region"] == "bay_of_bengal"
    assert data["source"] == "local_demo"
    assert len(data["points"]) == 1
    assert data["points"][0]["sensor_type"] == "buoy"
    assert data["points"][0]["sst_c"] == 29.4

    # Verify JSON string serialization
    json_str = snapshot.model_dump_json()
    parsed = json.loads(json_str)
    assert parsed["points"][0]["sensor_id"] == "buoy-bd08"


def test_region_bounds():
    bounds = RegionBounds(lat_min=5.0, lat_max=25.0, lon_min=80.0, lon_max=100.0)
    assert bounds.contains(15.0, 90.0) is True
    assert bounds.contains(30.0, 90.0) is False  # Out of latitude
    assert bounds.contains(15.0, 70.0) is False  # Out of longitude
