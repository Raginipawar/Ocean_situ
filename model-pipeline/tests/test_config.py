from pydantic import ValidationError

from varuna_model_pipeline.config import ModelPipelineSettings, RegionBounds
from varuna_model_pipeline.schema import CANONICAL_VARIABLES, ModelSource


def test_default_settings_match_bay_of_bengal_scope():
    settings = ModelPipelineSettings()

    assert settings.primary_source == ModelSource.INCOIS_LAS
    assert settings.fallback_source == ModelSource.COPERNICUS_GLORYS
    assert settings.demo_source == ModelSource.LOCAL_DEMO
    assert settings.region.name == "bay_of_bengal"
    assert settings.region.lat_min == 5.0
    assert settings.region.lat_max == 22.0
    assert settings.region.lon_min == 80.0
    assert settings.region.lon_max == 100.0
    assert settings.required_variables == tuple(CANONICAL_VARIABLES.keys())


def test_region_bounds_reject_inverted_latitude():
    try:
        RegionBounds(lat_min=22.0, lat_max=5.0)
    except ValidationError as exc:
        assert "lat_min must be less than lat_max" in str(exc)
    else:
        raise AssertionError("Expected invalid latitude bounds to fail")


def test_settings_reject_unknown_required_variable():
    try:
        ModelPipelineSettings(required_variables=("sst", "oxygen"))
    except ValidationError as exc:
        assert "Unknown canonical required variable" in str(exc)
    else:
        raise AssertionError("Expected unknown canonical variable to fail")

