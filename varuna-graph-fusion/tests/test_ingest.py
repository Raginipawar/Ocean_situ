from graph_fusion.ingest import parse_model_snapshot, parse_observation_snapshot


def test_parse_observation_snapshot_drops_malformed_points():
    raw = {
        "region": "bay_of_bengal",
        "source": "test",
        "points": [
            {"sensor_id": "s1", "sensor_type": "buoy", "lat": 10.0, "lon": 90.0, "sst_c": 28.0},
            {"sensor_id": "s2", "sensor_type": "buoy", "lat": 999.0, "lon": 90.0},  # lat out of range
            {"sensor_id": "s3", "sensor_type": "submarine_drone", "lat": 10.0, "lon": 90.0},  # bad enum
            {"sensor_type": "buoy", "lat": 10.0, "lon": 90.0},  # missing sensor_id
        ],
    }
    snap = parse_observation_snapshot(raw)
    assert len(snap.points) == 1
    assert snap.points[0].sensor_id == "s1"


def test_parse_observation_snapshot_all_valid_passes_through():
    raw = {
        "region": "bay_of_bengal",
        "points": [
            {"sensor_id": "s1", "sensor_type": "argo", "lat": 10.0, "lon": 90.0},
            {"sensor_id": "s2", "sensor_type": "mooring", "lat": 12.0, "lon": 91.0},
        ],
    }
    snap = parse_observation_snapshot(raw)
    assert len(snap.points) == 2
    assert {p.sensor_id for p in snap.points} == {"s1", "s2"}


def test_parse_observation_snapshot_extended_sensor_types_accepted():
    raw = {
        "region": "bay_of_bengal",
        "points": [
            {"sensor_id": "h1", "sensor_type": "hf_radar", "lat": 10.0, "lon": 90.0},
            {"sensor_id": "d1", "sensor_type": "drifter", "lat": 11.0, "lon": 91.0},
            {"sensor_id": "x1", "sensor_type": "xbt", "lat": 12.0, "lon": 92.0},
        ],
    }
    snap = parse_observation_snapshot(raw)
    assert len(snap.points) == 3


def test_parse_model_snapshot_drops_malformed_points():
    raw = {
        "region": "bay_of_bengal",
        "resolution_deg": 1.0,
        "points": [
            {"lat": 10.0, "lon": 90.0, "sst_c": 28.0},
            {"lat": "not-a-number", "lon": 90.0},
        ],
    }
    snap = parse_model_snapshot(raw)
    assert len(snap.points) == 1
    assert snap.points[0].sst_c == 28.0


def test_parse_model_snapshot_empty_points_still_constructs():
    raw = {"region": "bay_of_bengal", "resolution_deg": 1.0, "points": []}
    snap = parse_model_snapshot(raw)
    assert snap.points == []
    assert snap.region == "bay_of_bengal"
