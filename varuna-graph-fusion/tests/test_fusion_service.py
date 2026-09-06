import pytest

from graph_fusion.fallback_engine import FallbackFusionEngine
from graph_fusion.fusion_service import FusionService
from graph_fusion.schemas import ObservationPoint, ObservationSnapshot, SensorType


def test_fuse_auto_shape_and_ranges(sample_model, sample_obs):
    result = FusionService().fuse(sample_model, sample_obs, engine="auto")
    assert result.summary.engine in ("gnn", "fallback")
    assert len(result.points) == result.summary.n_sensors + result.summary.n_grid_points
    assert all(0.0 <= p.confidence <= 1.0 for p in result.points)
    assert all(p.trust_label in ("green", "amber", "red") for p in result.points)


def test_fuse_forced_fallback_has_no_validation_mae(sample_model, sample_obs):
    result = FusionService().fuse(sample_model, sample_obs, engine="fallback")
    assert result.summary.engine == "fallback"
    assert result.summary.validation_mae_sst_c is None


def test_fuse_forced_gnn_raises_with_too_few_sensors(sample_model):
    empty_obs = ObservationSnapshot(region="bay_of_bengal", points=[])
    with pytest.raises(RuntimeError):
        FusionService().fuse(sample_model, empty_obs, engine="gnn")


def test_fuse_auto_gracefully_degrades_with_too_few_sensors(sample_model):
    tiny_obs = ObservationSnapshot(
        region="bay_of_bengal",
        points=[
            ObservationPoint(
                sensor_id="s1", sensor_type=SensorType.BUOY, lat=13.0, lon=88.0, sst_c=29.0
            )
        ],
    )
    result = FusionService().fuse(sample_model, tiny_obs, engine="auto")
    assert result.summary.engine == "fallback"


def test_invalid_engine_raises_value_error(sample_model, sample_obs):
    with pytest.raises(ValueError):
        FusionService().fuse(sample_model, sample_obs, engine="bogus")


class _CountingFallback(FallbackFusionEngine):
    """Spy on FallbackFusionEngine.predict to prove caching skips recomputation."""

    def __init__(self):
        super().__init__()
        self.calls = 0

    def predict(self, fg):
        self.calls += 1
        return super().predict(fg)


def test_fuse_caches_identical_inputs(sample_model, sample_obs):
    counting = _CountingFallback()
    service = FusionService(fallback_engine=counting)

    r1 = service.fuse(sample_model, sample_obs, engine="fallback")
    r2 = service.fuse(sample_model, sample_obs, engine="fallback")

    assert counting.calls == 1
    assert r1.summary.n_sensors == r2.summary.n_sensors
    assert r1.points[0].correction_sst_c == r2.points[0].correction_sst_c


def test_fuse_cache_misses_on_different_inputs(sample_model):
    from graph_fusion import mock_data

    counting = _CountingFallback()
    service = FusionService(fallback_engine=counting)

    obs1 = mock_data.generate_mock_observations(n_sensors=10, seed=1)
    obs2 = mock_data.generate_mock_observations(n_sensors=10, seed=2)

    service.fuse(sample_model, obs1, engine="fallback")
    service.fuse(sample_model, obs2, engine="fallback")

    assert counting.calls == 2


def test_fuse_cache_ignores_volatile_timestamp(sample_model):
    """Mock sources stamp a fresh wall-clock time on every call; the cache key
    must be based on values, not that timestamp, or caching would never hit
    for the mock data path at all."""
    from datetime import datetime, timedelta, timezone

    counting = _CountingFallback()
    service = FusionService(fallback_engine=counting)

    obs = ObservationSnapshot(
        region="bay_of_bengal",
        points=[
            ObservationPoint(sensor_id="s1", sensor_type=SensorType.BUOY, lat=13.0, lon=88.0, sst_c=29.0)
        ],
    )
    obs_later = obs.model_copy(deep=True)
    obs_later.time = obs.time + timedelta(minutes=5)
    for p in obs_later.points:
        p.time = p.time + timedelta(minutes=5)

    service.fuse(sample_model, obs, engine="fallback")
    service.fuse(sample_model, obs_later, engine="fallback")

    assert counting.calls == 1


def test_fuse_sanitizes_sentinel_values_before_fusing(sample_model):
    """A sensor sending a QC fill value (-999) for SST must not be treated as
    a real -999C reading -- that residual would be background minus (-999),
    a ~1000C bogus correction. Sanitizing it to "no reading" means no
    correction gets applied at all (falls back to the model's own value)."""
    obs = ObservationSnapshot(
        region="bay_of_bengal",
        points=[
            ObservationPoint(
                sensor_id="s1", sensor_type=SensorType.BUOY, lat=13.0, lon=88.0, sst_c=-999.0
            )
        ],
    )
    result = FusionService().fuse(sample_model, obs, engine="fallback")
    sensor_point = next(p for p in result.points if p.is_sensor_node)
    assert sensor_point.correction_sst_c == 0.0
    assert sensor_point.sst_c is not None
    assert abs(sensor_point.correction_sst_c) < 5.0
