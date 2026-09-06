import numpy as np
import pytest
import xarray as xr

from varuna_model_pipeline.config import RegionBounds, TargetGridConfig
from varuna_model_pipeline.errors import MissingCoordinateError, MissingVariableError
from varuna_model_pipeline.processing.grid import build_target_grid
from varuna_model_pipeline.processing.regrid import RegriddingError, regrid_to_target
from varuna_model_pipeline.schema import CANONICAL_VARIABLES


def _dataset(lat=(5.0, 7.0), lon=(80.0, 82.0)):
    time = np.array(["2026-09-07T00:00:00"], dtype="datetime64[ns]")
    lat = np.array(lat, dtype=float)
    lon = np.array(lon, dtype=float)
    lon_grid, lat_grid = np.meshgrid(lon, lat)
    base = lat_grid + lon_grid
    shape = (1, len(lat), len(lon))
    vars_ = {}
    values_by_name = {
        "sst": base,
        "u_current": base / 100.0,
        "v_current": -base / 100.0,
        "wave_height": base / 100.0,
        "salinity": np.full_like(base, 34.0),
        "chlorophyll": np.full_like(base, 0.2),
    }
    for name, values in values_by_name.items():
        spec = CANONICAL_VARIABLES[name]
        vars_[name] = (
            ("time", "lat", "lon"),
            values.reshape(shape),
            {"units": spec.units, "standard_name": spec.standard_name},
        )
    return xr.Dataset(
        data_vars=vars_,
        coords={"time": time, "lat": lat, "lon": lon},
        attrs={
            "source": "LOCAL_DEMO",
            "region": "bay_of_bengal",
            "processing_level": "quality_checked",
            "target_resolution_deg": 1.0,
        },
    )


def test_build_target_grid_is_boundary_inclusive():
    grid = build_target_grid(
        RegionBounds(name="small", lat_min=5.0, lat_max=7.0, lon_min=80.0, lon_max=82.0),
        TargetGridConfig(resolution_deg=1.0),
    )

    assert grid.lat.values.tolist() == [5.0, 6.0, 7.0]
    assert grid.lon.values.tolist() == [80.0, 81.0, 82.0]


def test_regrid_linear_interpolates_to_common_grid():
    out = regrid_to_target(
        _dataset(),
        RegionBounds(name="small", lat_min=5.0, lat_max=7.0, lon_min=80.0, lon_max=82.0),
        TargetGridConfig(resolution_deg=1.0, method="linear"),
    )

    assert out.lat.values.tolist() == [5.0, 6.0, 7.0]
    assert out.lon.values.tolist() == [80.0, 81.0, 82.0]
    assert float(out["sst"].sel(time=out.time.values[0], lat=6.0, lon=81.0)) == pytest.approx(87.0)
    assert out.attrs["regridding_method"] == "linear"
    assert out.attrs["processing_level"] == "quality_checked+regridded"


def test_regrid_preserves_time_and_depth_dimensions():
    ds = _dataset()
    depth = np.array([0.0, 10.0])
    depth_values = np.stack([ds["u_current"].values[0], ds["u_current"].values[0] + 0.01])
    ds["u_current"] = (
        ("time", "depth", "lat", "lon"),
        depth_values.reshape(1, 2, 2, 2),
        ds["u_current"].attrs,
    )
    ds = ds.assign_coords(depth=depth)

    out = regrid_to_target(
        ds,
        RegionBounds(name="small", lat_min=5.0, lat_max=7.0, lon_min=80.0, lon_max=82.0),
        TargetGridConfig(resolution_deg=1.0, method="linear"),
    )

    assert out["u_current"].dims == ("time", "depth", "lat", "lon")
    assert out.depth.values.tolist() == [0.0, 10.0]


def test_regrid_sorts_descending_coordinates_before_interpolation():
    ds = _dataset(lat=(7.0, 5.0), lon=(82.0, 80.0))

    out = regrid_to_target(
        ds,
        RegionBounds(name="small", lat_min=5.0, lat_max=7.0, lon_min=80.0, lon_max=82.0),
        TargetGridConfig(resolution_deg=1.0, method="linear"),
    )

    assert out.lat.values.tolist() == [5.0, 6.0, 7.0]
    assert out.lon.values.tolist() == [80.0, 81.0, 82.0]


def test_regrid_preserves_nans_instead_of_fabricating_values():
    ds = _dataset()
    values = ds["sst"].values.copy()
    values[0, 0, 0] = np.nan
    ds["sst"] = (ds["sst"].dims, values, ds["sst"].attrs)

    out = regrid_to_target(
        ds,
        RegionBounds(name="small", lat_min=5.0, lat_max=7.0, lon_min=80.0, lon_max=82.0),
        TargetGridConfig(resolution_deg=1.0, method="linear"),
    )

    assert np.isnan(out["sst"].sel(time=out.time.values[0], lat=5.0, lon=80.0))


def test_regrid_rejects_missing_coordinate():
    ds = _dataset().drop_vars("lat")

    with pytest.raises(MissingCoordinateError, match="coordinate 'lat'"):
        regrid_to_target(ds, RegionBounds(), TargetGridConfig())


def test_regrid_rejects_missing_required_variable():
    ds = _dataset().drop_vars("chlorophyll")

    with pytest.raises(MissingVariableError, match="chlorophyll"):
        regrid_to_target(ds, RegionBounds(), TargetGridConfig())


def test_regrid_rejects_duplicate_coordinates():
    ds = _dataset(lat=(5.0, 5.0), lon=(80.0, 82.0))

    with pytest.raises(RegriddingError, match="duplicate"):
        regrid_to_target(ds, RegionBounds(), TargetGridConfig())

