from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from varuna_model_pipeline.errors import (
    MissingCoordinateError,
    MissingVariableError,
    UnsupportedUnitError,
)
from varuna_model_pipeline.schema import CANONICAL_VARIABLES
from varuna_model_pipeline.sources.incois_las import IncoisLasIngestor


def _incois_fixture_dataset() -> xr.Dataset:
    time = np.array(["2026-09-07T00:00:00"], dtype="datetime64[ns]")
    depth = np.array([0.0, 10.0])
    lat = np.array([5.0, 6.0])
    lon = np.array([80.0, 81.0])

    surface_shape = (1, 2, 2)
    depth_shape = (1, 2, 2, 2)

    ds = xr.Dataset(
        data_vars={
            "temp": (
                ("TIME", "Latitude", "Longitude"),
                np.full(surface_shape, 28.5),
                {"units": "degC", "standard_name": "sea_surface_temperature"},
            ),
            "u": (
                ("TIME", "Depth", "Latitude", "Longitude"),
                np.full(depth_shape, 0.12),
                {"units": "m s-1", "standard_name": "eastward_sea_water_velocity"},
            ),
            "v": (
                ("TIME", "Depth", "Latitude", "Longitude"),
                np.full(depth_shape, -0.04),
                {"units": "m s-1", "standard_name": "northward_sea_water_velocity"},
            ),
            "hs": (
                ("TIME", "Latitude", "Longitude"),
                np.full(surface_shape, 1.4),
                {"units": "m", "standard_name": "sea_surface_wave_significant_height"},
            ),
            "salt": (
                ("TIME", "Depth", "Latitude", "Longitude"),
                np.full(depth_shape, 34.1),
                {"units": "psu", "standard_name": "sea_water_practical_salinity"},
            ),
            "chl": (
                ("TIME", "Latitude", "Longitude"),
                np.full(surface_shape, 0.23),
                {
                    "units": "mg m-3",
                    "standard_name": "mass_concentration_of_chlorophyll_a_in_sea_water",
                },
            ),
        },
        coords={
            "TIME": time,
            "Depth": depth,
            "Latitude": lat,
            "Longitude": lon,
        },
        attrs={"title": "Synthetic INCOIS LAS fixture"},
    )
    return ds


def test_standardize_maps_incois_variables_to_canonical_schema():
    result = IncoisLasIngestor().standardize(_incois_fixture_dataset(), source_path="fixture.nc")

    assert result.source_path == "fixture.nc"
    assert result.coordinate_mapping == {
        "time": "TIME",
        "lat": "Latitude",
        "lon": "Longitude",
        "depth": "Depth",
    }
    assert result.variable_mapping == {
        "temp": "sst",
        "u": "u_current",
        "v": "v_current",
        "hs": "wave_height",
        "salt": "salinity",
        "chl": "chlorophyll",
    }
    assert set(result.dataset.data_vars) == set(CANONICAL_VARIABLES)
    assert set(("time", "lat", "lon", "depth")).issubset(result.dataset.coords)
    assert result.dataset.attrs["source"] == "INCOIS_LAS"
    assert result.dataset.attrs["source_url"] == "fixture.nc"
    assert result.dataset["sst"].attrs["source_variable"] == "temp"


def test_load_reads_local_netcdf_fixture(tmp_path: Path):
    path = tmp_path / "incois_fixture.nc"
    _incois_fixture_dataset().to_netcdf(path)

    result = IncoisLasIngestor().load(path)

    assert result.source_path == str(path)
    assert "sst" in result.dataset.data_vars
    assert float(result.dataset["sst"].isel(time=0, lat=0, lon=0)) == 28.5


def test_missing_coordinate_fails_clearly():
    ds = _incois_fixture_dataset().drop_vars("Latitude")

    with pytest.raises(MissingCoordinateError, match="missing required coordinate 'lat'"):
        IncoisLasIngestor().standardize(ds)


def test_missing_required_variable_fails_clearly():
    ds = _incois_fixture_dataset().drop_vars("chl")

    with pytest.raises(MissingVariableError, match="chlorophyll"):
        IncoisLasIngestor().standardize(ds)


def test_unsupported_units_fail_instead_of_guessing():
    ds = _incois_fixture_dataset()
    ds["temp"].attrs["units"] = "kelvin"

    with pytest.raises(UnsupportedUnitError, match="unsupported units 'kelvin'"):
        IncoisLasIngestor().standardize(ds)

