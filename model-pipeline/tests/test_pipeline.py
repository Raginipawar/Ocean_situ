from pathlib import Path

import numpy as np
import xarray as xr

from varuna_model_pipeline.config import ModelPipelineSettings, RegionBounds, TargetGridConfig
from varuna_model_pipeline.pipeline import (
    load_local_demo_model_data,
    prepare_model_dataset,
    process_model_data,
)
from varuna_model_pipeline.schema import CANONICAL_VARIABLES, ModelSource


def _incois_fixture_dataset() -> xr.Dataset:
    time = np.array(["2026-09-07T00:00:00"], dtype="datetime64[ns]")
    depth = np.array([0.0, 10.0])
    lat = np.array([4.0, 5.0, 6.0, 7.0])
    lon = np.array([79.0, 80.0, 81.0, 82.0])
    surface_shape = (1, 4, 4)
    depth_shape = (1, 2, 4, 4)
    return xr.Dataset(
        data_vars={
            "temp": (("TIME", "Latitude", "Longitude"), np.full(surface_shape, 28.0), {"units": "degC"}),
            "u": (("TIME", "Depth", "Latitude", "Longitude"), np.full(depth_shape, 0.1), {"units": "m s-1"}),
            "v": (("TIME", "Depth", "Latitude", "Longitude"), np.full(depth_shape, 0.2), {"units": "m s-1"}),
            "hs": (("TIME", "Latitude", "Longitude"), np.full(surface_shape, 1.3), {"units": "m"}),
            "salt": (("TIME", "Depth", "Latitude", "Longitude"), np.full(depth_shape, 34.0), {"units": "psu"}),
            "chl": (("TIME", "Latitude", "Longitude"), np.full(surface_shape, 0.2), {"units": "mg m-3"}),
        },
        coords={"TIME": time, "Depth": depth, "Latitude": lat, "Longitude": lon},
    )


def _glorys_fixture_dataset() -> xr.Dataset:
    time = np.array(["2026-09-07T00:00:00"], dtype="datetime64[ns]")
    depth = np.array([0.0, 10.0])
    lat = np.array([4.0, 5.0, 6.0, 7.0])
    lon = np.array([79.0, 80.0, 81.0, 82.0])
    surface_shape = (1, 4, 4)
    depth_shape = (1, 2, 4, 4)
    return xr.Dataset(
        data_vars={
            "thetao": (("time", "depth", "latitude", "longitude"), np.full(depth_shape, 28.1), {"units": "degC"}),
            "uo": (("time", "depth", "latitude", "longitude"), np.full(depth_shape, 0.11), {"units": "m s-1"}),
            "vo": (("time", "depth", "latitude", "longitude"), np.full(depth_shape, 0.19), {"units": "m s-1"}),
            "VHM0": (("time", "latitude", "longitude"), np.full(surface_shape, 1.35), {"units": "m"}),
            "so": (("time", "depth", "latitude", "longitude"), np.full(depth_shape, 34.2), {"units": "1e-3"}),
            "chl": (("time", "latitude", "longitude"), np.full(surface_shape, 0.21), {"units": "mg m-3"}),
        },
        coords={"time": time, "depth": depth, "latitude": lat, "longitude": lon},
    )


def _settings() -> ModelPipelineSettings:
    return ModelPipelineSettings(
        region=RegionBounds(name="small", lat_min=5.0, lat_max=7.0, lon_min=80.0, lon_max=82.0),
        target_grid=TargetGridConfig(resolution_deg=1.0, method="linear"),
    )


def test_process_model_data_composes_region_normalize_quality_and_regrid():
    from varuna_model_pipeline.sources.incois_las import IncoisLasIngestor

    ingested = IncoisLasIngestor(settings=_settings()).standardize(_incois_fixture_dataset()).dataset
    processed = process_model_data(ingested, settings=_settings())

    assert processed.lat.values.tolist() == [5.0, 6.0, 7.0]
    assert processed.lon.values.tolist() == [80.0, 81.0, 82.0]
    assert set(processed.data_vars) == set(CANONICAL_VARIABLES)
    assert processed.attrs["pipeline_stages"] == "extract_region,normalize_and_quality_check,regrid_to_common_target"
    assert processed.attrs["processing_level"].endswith("quality_checked+regridded")


def test_prepare_model_dataset_uses_incois_when_primary_succeeds(tmp_path: Path):
    primary = tmp_path / "incois.nc"
    fallback = tmp_path / "glorys.nc"
    _incois_fixture_dataset().to_netcdf(primary)
    _glorys_fixture_dataset().to_netcdf(fallback)

    result = prepare_model_dataset(primary_path=primary, fallback_path=fallback, settings=_settings())

    assert result.source == ModelSource.INCOIS_LAS
    assert result.dataset.sizes["lat"] == 3
    assert result.dataset.sizes["lon"] == 3
    assert result.stages == ["load_primary_or_fallback", "process_model_data"]


def test_prepare_model_dataset_uses_glorys_after_primary_failure(tmp_path: Path):
    primary = tmp_path / "broken.nc"
    fallback = tmp_path / "glorys.nc"
    primary.write_text("not netcdf", encoding="utf-8")
    _glorys_fixture_dataset().to_netcdf(fallback)

    result = prepare_model_dataset(primary_path=primary, fallback_path=fallback, settings=_settings())

    assert result.source == ModelSource.COPERNICUS_GLORYS
    assert [attempt.ok for attempt in result.attempts] == [False, True]
    assert result.dataset.attrs["source"] == ModelSource.COPERNICUS_GLORYS.value


def test_local_demo_pipeline_is_deterministic_and_common_grid_aligned():
    settings = ModelPipelineSettings(target_grid=TargetGridConfig(resolution_deg=2.0, method="linear"))

    first = load_local_demo_model_data(settings=settings)
    second = load_local_demo_model_data(settings=settings)

    assert first.source == ModelSource.LOCAL_DEMO
    assert first.dataset.lat.values.tolist() == second.dataset.lat.values.tolist()
    assert first.dataset.lon.values.tolist() == second.dataset.lon.values.tolist()
    np.testing.assert_allclose(first.dataset["sst"].values, second.dataset["sst"].values)
    assert first.dataset.attrs["source"] == ModelSource.LOCAL_DEMO.value

