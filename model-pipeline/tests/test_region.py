import numpy as np
import pytest
import xarray as xr

from varuna_model_pipeline.config import RegionBounds
from varuna_model_pipeline.errors import MissingCoordinateError
from varuna_model_pipeline.processing.region import EmptyRegionError, extract_region


def _dataset(lat, lon):
    time = np.array(["2026-09-07T00:00:00"], dtype="datetime64[ns]")
    values = np.arange(len(time) * len(lat) * len(lon), dtype=float).reshape(
        len(time), len(lat), len(lon)
    )
    return xr.Dataset(
        data_vars={"sst": (("time", "lat", "lon"), values, {"units": "degC"})},
        coords={"time": time, "lat": np.array(lat, dtype=float), "lon": np.array(lon, dtype=float)},
        attrs={"source": "LOCAL_DEMO", "processing_level": "canonical_schema"},
    )


def test_extract_region_with_ascending_coordinates():
    ds = _dataset(lat=[4, 5, 10, 22, 23], lon=[79, 80, 90, 100, 101])

    out = extract_region(ds, RegionBounds())

    assert out.lat.values.tolist() == [5.0, 10.0, 22.0]
    assert out.lon.values.tolist() == [80.0, 90.0, 100.0]
    assert out.attrs["region"] == "bay_of_bengal"
    assert out.attrs["processing_level"] == "canonical_schema+region_extracted"


def test_extract_region_with_descending_latitude():
    ds = _dataset(lat=[23, 22, 10, 5, 4], lon=[79, 80, 90, 100, 101])

    out = extract_region(ds, RegionBounds())

    assert out.lat.values.tolist() == [5.0, 10.0, 22.0]
    assert out.lon.values.tolist() == [80.0, 90.0, 100.0]


def test_extract_region_normalizes_zero_to_360_longitudes():
    ds = _dataset(lat=[5, 10, 22], lon=[79, 80, 90, 100, 190, 350])
    arabian_sea = RegionBounds(name="western_test", lat_min=4, lat_max=12, lon_min=-20, lon_max=-5)

    out = extract_region(ds, arabian_sea)

    assert out.lon.values.tolist() == [-10.0]
    assert out.attrs["region"] == "western_test"


def test_extract_region_includes_boundary_points():
    ds = _dataset(lat=[5.0, 22.0], lon=[80.0, 100.0])

    out = extract_region(ds, RegionBounds())

    assert out.sizes["lat"] == 2
    assert out.sizes["lon"] == 2


def test_extract_region_rejects_empty_region():
    ds = _dataset(lat=[-20, -10], lon=[10, 20])

    with pytest.raises(EmptyRegionError, match="contains no coordinate points"):
        extract_region(ds, RegionBounds())


def test_extract_region_requires_lat_lon_coordinates():
    ds = _dataset(lat=[5, 10], lon=[80, 90]).drop_vars("lat")

    with pytest.raises(MissingCoordinateError, match="missing coordinate 'lat'"):
        extract_region(ds, RegionBounds())

