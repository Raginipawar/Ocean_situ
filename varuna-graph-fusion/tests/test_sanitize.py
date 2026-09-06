from graph_fusion.sanitize import sanitize_model, sanitize_observations
from graph_fusion.schemas import (
    ModelGridPoint,
    ModelSnapshot,
    ObservationPoint,
    ObservationSnapshot,
    SensorType,
)


def test_sentinel_values_become_none_in_model():
    model = ModelSnapshot(
        region="test",
        resolution_deg=1.0,
        points=[
            ModelGridPoint(lat=10, lon=90, sst_c=-999.0, current_u_ms=0.1, current_v_ms=0.1, wave_height_m=1.0),
        ],
    )
    cleaned, n = sanitize_model(model)
    assert n == 1
    assert cleaned.points[0].sst_c is None
    assert cleaned.points[0].current_u_ms == 0.1  # untouched


def test_out_of_range_values_become_none_in_observations():
    obs = ObservationSnapshot(
        region="test",
        points=[ObservationPoint(sensor_id="s1", sensor_type=SensorType.BUOY, lat=10, lon=90, sst_c=85.0)],
    )
    cleaned, n = sanitize_observations(obs)
    assert n == 1
    assert cleaned.points[0].sst_c is None


def test_valid_values_untouched():
    obs = ObservationSnapshot(
        region="test",
        points=[
            ObservationPoint(
                sensor_id="s1", sensor_type=SensorType.BUOY, lat=10, lon=90, sst_c=28.5, current_u_ms=0.2
            )
        ],
    )
    cleaned, n = sanitize_observations(obs)
    assert n == 0
    assert cleaned.points[0].sst_c == 28.5
    assert cleaned.points[0].current_u_ms == 0.2


def test_already_none_values_stay_none_and_are_not_counted():
    obs = ObservationSnapshot(
        region="test",
        points=[ObservationPoint(sensor_id="s1", sensor_type=SensorType.BUOY, lat=10, lon=90)],
    )
    cleaned, n = sanitize_observations(obs)
    assert n == 0
    assert cleaned.points[0].sst_c is None


def test_current_speed_out_of_physical_range_is_dropped():
    obs = ObservationSnapshot(
        region="test",
        points=[
            ObservationPoint(
                sensor_id="s1", sensor_type=SensorType.BUOY, lat=10, lon=90, current_u_ms=50.0
            )
        ],
    )
    cleaned, n = sanitize_observations(obs)
    assert n == 1
    assert cleaned.points[0].current_u_ms is None
