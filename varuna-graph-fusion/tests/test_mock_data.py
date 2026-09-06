import numpy as np

from graph_fusion import config, mock_data


def test_model_grid_within_region_bounds():
    snap = mock_data.generate_mock_model_grid(resolution_deg=2.0)
    assert len(snap.points) > 0
    for p in snap.points:
        assert config.LAT_MIN <= p.lat <= config.LAT_MAX
        assert config.LON_MIN <= p.lon <= config.LON_MAX
        assert 15.0 <= p.sst_c <= 35.0  # physically sane SST for the Bay of Bengal


def test_observations_shape_and_types():
    obs = mock_data.generate_mock_observations(n_sensors=25, seed=1)
    assert len(obs.points) == 25
    sensor_types = {p.sensor_type for p in obs.points}
    assert sensor_types.issubset({"argo", "glider", "ctd", "buoy"})
    for p in obs.points:
        assert config.LAT_MIN <= p.lat <= config.LAT_MAX
        assert config.LON_MIN <= p.lon <= config.LON_MAX
        assert p.depth_m >= 0.0


def test_observations_reproducible_with_seed():
    obs1 = mock_data.generate_mock_observations(n_sensors=10, seed=42)
    obs2 = mock_data.generate_mock_observations(n_sensors=10, seed=42)
    assert [p.lat for p in obs1.points] == [p.lat for p in obs2.points]
    assert [p.sst_c for p in obs1.points] == [p.sst_c for p in obs2.points]


def test_heatwave_sensors_have_larger_residual_than_far_field_sensors():
    """
    Sanity check on the synthetic data itself: sensors sampled from inside the
    injected marine-heatwave patch should read noticeably warmer than the
    model's background field at the same location, since the model does not
    know about the heatwave. This is the divergence signal the fusion engine
    is supposed to recover.
    """
    obs = mock_data.generate_mock_observations(n_sensors=200, seed=3, heatwave_fraction=0.3)
    model_bg = mock_data.model_fields(
        np.array([p.lat for p in obs.points]), np.array([p.lon for p in obs.points])
    )["sst_c"]
    residual = np.array([p.sst_c for p in obs.points]) - model_bg

    heatwave_center_lat, heatwave_center_lon = mock_data._HEATWAVE_CENTER
    dist = np.hypot(
        np.array([p.lat for p in obs.points]) - heatwave_center_lat,
        np.array([p.lon for p in obs.points]) - heatwave_center_lon,
    )
    near_mean = residual[dist < 1.5].mean()
    far_mean = residual[dist > 5.0].mean()
    assert near_mean > far_mean + 0.5
