import numpy as np
import pytest
import xarray as xr

from varuna_model_pipeline.errors import MissingVariableError, UnsupportedUnitError
from varuna_model_pipeline.processing.normalize import normalize_model_dataset
from varuna_model_pipeline.processing.quality import validate_quality
from varuna_model_pipeline.processing.units import normalize_units


def _canonical_dataset(**overrides):
    time = np.array(["2026-09-07T00:00:00"], dtype="datetime64[ns]")
    lat = np.array([5.0, 6.0])
    lon = np.array([80.0, 81.0])
    shape = (1, 2, 2)
    vars_ = {
        "sst": (("time", "lat", "lon"), np.full(shape, 301.15), {"units": "K"}),
        "u_current": (("time", "lat", "lon"), np.full(shape, 12.0), {"units": "cm/s"}),
        "v_current": (("time", "lat", "lon"), np.full(shape, -4.0), {"units": "cm s-1"}),
        "wave_height": (("time", "lat", "lon"), np.full(shape, 140.0), {"units": "cm"}),
        "salinity": (("time", "lat", "lon"), np.full(shape, 34.0), {"units": "psu"}),
        "chlorophyll": (("time", "lat", "lon"), np.full(shape, 0.2), {"units": "mg/m^3"}),
    }
    vars_.update(overrides.pop("data_vars", {}))
    return xr.Dataset(
        data_vars=vars_,
        coords=overrides.pop("coords", {"time": time, "lat": lat, "lon": lon, "depth": [0.0]}),
        attrs=overrides.pop(
            "attrs",
            {
                "source": "LOCAL_DEMO",
                "region": "bay_of_bengal",
                "processing_level": "region_extracted",
                "target_resolution_deg": 1.0,
            },
        ),
    )


def test_normalize_units_converts_only_explicit_supported_units():
    out = normalize_units(_canonical_dataset())

    assert out["sst"].attrs["units"] == "degC"
    assert float(out["sst"].isel(time=0, lat=0, lon=0)) == pytest.approx(28.0)
    assert out["u_current"].attrs["units"] == "m s-1"
    assert float(out["u_current"].isel(time=0, lat=0, lon=0)) == pytest.approx(0.12)
    assert float(out["wave_height"].isel(time=0, lat=0, lon=0)) == pytest.approx(1.4)


def test_normalize_units_rejects_unsupported_units():
    ds = _canonical_dataset(
        data_vars={
            "sst": (("time", "lat", "lon"), np.full((1, 2, 2), 28.0), {"units": "fahrenheit"})
        }
    )

    with pytest.raises(UnsupportedUnitError, match="unsupported unit conversion"):
        normalize_units(ds)


def test_quality_reports_nan_warning_but_passes_below_threshold():
    ds = normalize_units(_canonical_dataset())
    values = ds["sst"].values.copy()
    values[0, 0, 0] = np.nan
    ds["sst"] = (ds["sst"].dims, values, ds["sst"].attrs)

    report = validate_quality(ds, max_nan_fraction=0.5)

    assert report.ok
    assert any(issue.code == "nan_values" and issue.severity == "warning" for issue in report.issues)


def test_quality_rejects_inf_values():
    ds = normalize_units(_canonical_dataset())
    values = ds["u_current"].values.copy()
    values[0, 0, 0] = np.inf
    ds["u_current"] = (ds["u_current"].dims, values, ds["u_current"].attrs)

    report = validate_quality(ds)

    assert not report.ok
    assert any(issue.code == "inf_values" for issue in report.errors)


def test_quality_rejects_impossible_values():
    ds = normalize_units(_canonical_dataset())
    values = ds["wave_height"].values.copy()
    values[0, 0, 0] = 99.0
    ds["wave_height"] = (ds["wave_height"].dims, values, ds["wave_height"].attrs)

    report = validate_quality(ds)

    assert not report.ok
    assert any(issue.code == "impossible_value" for issue in report.errors)


def test_quality_rejects_duplicate_coordinates():
    ds = normalize_units(
        _canonical_dataset(coords={"time": ["2026-09-07"], "lat": [5.0, 5.0], "lon": [80.0, 81.0], "depth": [0.0]})
    )

    report = validate_quality(ds)

    assert not report.ok
    assert any(issue.code == "duplicate_coordinate" for issue in report.errors)


def test_quality_rejects_malformed_timestamps():
    ds = normalize_units(
        _canonical_dataset(coords={"time": ["not-a-real-time"], "lat": [5.0, 6.0], "lon": [80.0, 81.0], "depth": [0.0]})
    )

    report = validate_quality(ds)

    assert not report.ok
    assert any(issue.code == "malformed_timestamp" for issue in report.errors)


def test_normalize_model_dataset_rejects_missing_required_variable():
    ds = _canonical_dataset().drop_vars("chlorophyll")

    with pytest.raises(MissingVariableError, match="chlorophyll"):
        normalize_model_dataset(ds)


def test_normalize_model_dataset_returns_quality_checked_dataset():
    out, report = normalize_model_dataset(_canonical_dataset())

    assert report.ok
    assert out.attrs["processing_level"] == "region_extracted+units_normalized+quality_checked"
    assert set(out.data_vars) == {
        "sst",
        "u_current",
        "v_current",
        "wave_height",
        "salinity",
        "chlorophyll",
    }

