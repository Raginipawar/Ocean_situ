from types import SimpleNamespace

from pydantic import ValidationError

from varuna_model_pipeline.schema import (
    CANONICAL_VARIABLES,
    CanonicalDatasetMetadata,
    ModelSource,
    build_default_metadata,
    validate_dataset_like,
)


class FakeDataset:
    def __init__(self, *, coords, data_vars, attrs):
        self.coords = coords
        self.data_vars = data_vars
        self.attrs = attrs


def _fake_var(units: str):
    return SimpleNamespace(attrs={"units": units})


def test_canonical_variables_include_required_model_fields():
    assert set(CANONICAL_VARIABLES) == {
        "sst",
        "u_current",
        "v_current",
        "wave_height",
        "salinity",
        "chlorophyll",
    }
    assert CANONICAL_VARIABLES["sst"].api_name == "sst_c"
    assert CANONICAL_VARIABLES["u_current"].api_name == "current_u_ms"
    assert CANONICAL_VARIABLES["v_current"].api_name == "current_v_ms"
    assert CANONICAL_VARIABLES["wave_height"].api_name == "wave_height_m"


def test_default_metadata_preserves_source_provenance():
    metadata = build_default_metadata(
        source=ModelSource.INCOIS_LAS,
        source_url="https://example.invalid/las",
        target_resolution_deg=0.25,
    )

    assert metadata.source == ModelSource.INCOIS_LAS
    assert metadata.source_url == "https://example.invalid/las"
    assert metadata.target_resolution_deg == 0.25
    assert set(metadata.variables) == set(CANONICAL_VARIABLES)


def test_metadata_requires_all_canonical_variables():
    try:
        CanonicalDatasetMetadata(
            source=ModelSource.LOCAL_DEMO,
            target_resolution_deg=1.0,
            variables={"sst": CANONICAL_VARIABLES["sst"]},
        )
    except ValidationError as exc:
        assert "Missing canonical variable metadata" in str(exc)
    else:
        raise AssertionError("Expected incomplete metadata to fail")


def test_validate_dataset_like_accepts_complete_schema():
    data_vars = {
        name: _fake_var(spec.units)
        for name, spec in CANONICAL_VARIABLES.items()
    }
    dataset = FakeDataset(
        coords={"time": object(), "lat": object(), "lon": object(), "depth": object()},
        data_vars=data_vars,
        attrs={
            "source": "LOCAL_DEMO",
            "region": "bay_of_bengal",
            "processing_level": "canonical_schema",
            "target_resolution_deg": 1.0,
        },
    )

    report = validate_dataset_like(dataset)

    assert report.ok
    assert report.errors == []


def test_validate_dataset_like_reports_missing_variable_and_bad_units():
    data_vars = {
        name: _fake_var(spec.units)
        for name, spec in CANONICAL_VARIABLES.items()
        if name != "chlorophyll"
    }
    data_vars["sst"] = _fake_var("kelvin")
    dataset = FakeDataset(
        coords={"time": object(), "lat": object(), "lon": object()},
        data_vars=data_vars,
        attrs={
            "source": "LOCAL_DEMO",
            "region": "bay_of_bengal",
            "processing_level": "canonical_schema",
            "target_resolution_deg": 1.0,
        },
    )

    report = validate_dataset_like(dataset)

    assert not report.ok
    assert "Missing canonical variable: chlorophyll" in report.errors
    assert "sst: expected units 'degC', found 'kelvin'" in report.errors
    assert report.warnings

