from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from varuna_model_pipeline.errors import IngestionError, MissingVariableError
from varuna_model_pipeline.schema import CANONICAL_VARIABLES, ModelSource
from varuna_model_pipeline.source_selection import load_with_explicit_fallback
from varuna_model_pipeline.sources.glorys import GlorysIngestor
from varuna_model_pipeline.sources.incois_las import IncoisLasIngestor


def _incois_fixture_dataset() -> xr.Dataset:
    time = np.array(["2026-09-07T00:00:00"], dtype="datetime64[ns]")
    depth = np.array([0.0, 10.0])
    lat = np.array([5.0, 6.0])
    lon = np.array([80.0, 81.0])
    surface_shape = (1, 2, 2)
    depth_shape = (1, 2, 2, 2)

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
    latitude = np.array([5.0, 6.0])
    longitude = np.array([80.0, 81.0])
    surface_shape = (1, 2, 2)
    depth_shape = (1, 2, 2, 2)

    return xr.Dataset(
        data_vars={
            "thetao": (("time", "depth", "latitude", "longitude"), np.full(depth_shape, 28.1), {"units": "degC"}),
            "uo": (("time", "depth", "latitude", "longitude"), np.full(depth_shape, 0.11), {"units": "m s-1"}),
            "vo": (("time", "depth", "latitude", "longitude"), np.full(depth_shape, 0.19), {"units": "m s-1"}),
            "VHM0": (("time", "latitude", "longitude"), np.full(surface_shape, 1.35), {"units": "m"}),
            "so": (("time", "depth", "latitude", "longitude"), np.full(depth_shape, 34.2), {"units": "1e-3"}),
            "chl": (("time", "latitude", "longitude"), np.full(surface_shape, 0.21), {"units": "mg m-3"}),
        },
        coords={"time": time, "depth": depth, "latitude": latitude, "longitude": longitude},
    )


def test_glorys_standardizes_to_same_canonical_schema_as_incois():
    incois = IncoisLasIngestor().standardize(_incois_fixture_dataset()).dataset
    glorys = GlorysIngestor().standardize(_glorys_fixture_dataset()).dataset

    assert set(incois.data_vars) == set(glorys.data_vars) == set(CANONICAL_VARIABLES)
    assert set(("time", "lat", "lon", "depth")).issubset(glorys.coords)
    assert glorys.attrs["source"] == ModelSource.COPERNICUS_GLORYS.value
    assert glorys["sst"].attrs["source_variable"] == "thetao"
    assert glorys["u_current"].attrs["source_variable"] == "uo"
    assert glorys["v_current"].attrs["source_variable"] == "vo"


def test_glorys_missing_variable_fails_clearly():
    ds = _glorys_fixture_dataset().drop_vars("so")

    with pytest.raises(MissingVariableError, match="salinity"):
        GlorysIngestor().standardize(ds)


def test_source_selection_uses_incois_when_primary_succeeds(tmp_path: Path):
    primary = tmp_path / "incois.nc"
    fallback = tmp_path / "glorys.nc"
    _incois_fixture_dataset().to_netcdf(primary)
    _glorys_fixture_dataset().to_netcdf(fallback)

    selected = load_with_explicit_fallback(primary_path=primary, fallback_path=fallback)

    assert selected.source == ModelSource.INCOIS_LAS
    assert selected.source_path == str(primary)
    assert [attempt.source for attempt in selected.attempts] == [ModelSource.INCOIS_LAS]
    assert selected.attempts[0].ok


def test_source_selection_records_primary_failure_then_uses_glorys(tmp_path: Path):
    primary = tmp_path / "broken_incois.nc"
    fallback = tmp_path / "glorys.nc"
    primary.write_text("not a netcdf file", encoding="utf-8")
    _glorys_fixture_dataset().to_netcdf(fallback)

    selected = load_with_explicit_fallback(primary_path=primary, fallback_path=fallback)

    assert selected.source == ModelSource.COPERNICUS_GLORYS
    assert selected.source_path == str(fallback)
    assert [attempt.source for attempt in selected.attempts] == [
        ModelSource.INCOIS_LAS,
        ModelSource.COPERNICUS_GLORYS,
    ]
    assert not selected.attempts[0].ok
    assert selected.attempts[0].error
    assert selected.attempts[1].ok


def test_source_selection_fails_when_both_sources_fail(tmp_path: Path):
    primary = tmp_path / "broken_incois.nc"
    fallback = tmp_path / "broken_glorys.nc"
    primary.write_text("not netcdf", encoding="utf-8")
    fallback.write_text("also not netcdf", encoding="utf-8")

    with pytest.raises(IngestionError, match="Both INCOIS LAS primary and GLORYS fallback"):
        load_with_explicit_fallback(primary_path=primary, fallback_path=fallback)


def test_source_selection_fetches_live_glorys_when_flag_set_and_no_fallback_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """use_live_glorys_fallback=True + no local fallback file -> the live
    fetch (sources/glorys_live.py) is used to produce the fallback path,
    instead of raising "no fallback provided"."""
    from varuna_model_pipeline.config import ModelPipelineSettings

    fallback = tmp_path / "live_glorys.nc"
    _glorys_fixture_dataset().to_netcdf(fallback)

    def fake_fetch_live_glorys_window(*, settings, lookback_days):
        assert lookback_days == 3
        return fallback

    monkeypatch.setattr(
        "varuna_model_pipeline.sources.glorys_live.fetch_live_glorys_window",
        fake_fetch_live_glorys_window,
    )

    cfg = ModelPipelineSettings(use_live_glorys_fallback=True, live_glorys_lookback_days=3)
    selected = load_with_explicit_fallback(primary_path=None, fallback_path=None, settings=cfg)

    assert selected.source == ModelSource.COPERNICUS_GLORYS
    assert selected.source_path == str(fallback)


def test_source_selection_raises_no_fallback_when_live_fetch_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A live-fetch failure (no network, no `copernicusmarine login`) is
    recorded as a failed attempt, not raised directly -- it falls through to
    the same "no fallback available" error a missing local path gives."""
    from varuna_model_pipeline.config import ModelPipelineSettings

    def fake_fetch_live_glorys_window(*, settings, lookback_days):
        raise RuntimeError("not logged in")

    monkeypatch.setattr(
        "varuna_model_pipeline.sources.glorys_live.fetch_live_glorys_window",
        fake_fetch_live_glorys_window,
    )

    cfg = ModelPipelineSettings(use_live_glorys_fallback=True)
    with pytest.raises(IngestionError, match="no GLORYS fallback path was provided"):
        load_with_explicit_fallback(primary_path=None, fallback_path=None, settings=cfg)

