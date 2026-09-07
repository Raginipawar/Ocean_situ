"""
Tests for the live GLORYS fetch contribution (glorys_live.py).

Deliberately mocks `copernicusmarine.subset` -- unit tests should never
depend on live network access or a machine having run `copernicusmarine
login`. The real, unmocked path was exercised manually while gathering data
for the Nowcast Engine (see varuna-streaming-nowcast/), confirmed to
produce genuine Copernicus Marine NetCDF files that GlorysIngestor parses
correctly.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest

from varuna_model_pipeline.config import ModelPipelineSettings


def _install_fake_copernicusmarine(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """copernicusmarine is an optional dependency; fake it out so this test
    suite doesn't require it to be installed."""
    fake_module = ModuleType("copernicusmarine")
    mock_subset = MagicMock()
    fake_module.subset = mock_subset  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "copernicusmarine", fake_module)
    return mock_subset


def test_fetch_live_glorys_window_calls_subset_with_configured_region(monkeypatch, tmp_path):
    from varuna_model_pipeline.sources.glorys_live import fetch_live_glorys_window

    mock_subset = _install_fake_copernicusmarine(monkeypatch)
    settings = ModelPipelineSettings()

    result_path = fetch_live_glorys_window(
        settings=settings,
        lookback_days=3,
        output_dir=tmp_path,
    )

    assert result_path.parent == tmp_path
    assert result_path.suffix == ".nc"

    mock_subset.assert_called_once()
    _, kwargs = mock_subset.call_args
    assert kwargs["minimum_longitude"] == settings.region.lon_min
    assert kwargs["maximum_longitude"] == settings.region.lon_max
    assert kwargs["minimum_latitude"] == settings.region.lat_min
    assert kwargs["maximum_latitude"] == settings.region.lat_max
    assert kwargs["output_directory"] == str(tmp_path)


def test_fetch_live_glorys_window_uses_custom_variables_and_dataset(monkeypatch, tmp_path):
    from varuna_model_pipeline.sources.glorys_live import fetch_live_glorys_window

    mock_subset = _install_fake_copernicusmarine(monkeypatch)

    fetch_live_glorys_window(
        dataset_id="cmems_mod_glo_wav_my_0.2deg_PT3H-i",
        variables=["VHM0"],
        output_dir=tmp_path,
    )

    _, kwargs = mock_subset.call_args
    assert kwargs["dataset_id"] == "cmems_mod_glo_wav_my_0.2deg_PT3H-i"
    assert kwargs["variables"] == ["VHM0"]


def test_fetch_live_glorys_window_raises_clear_error_without_copernicusmarine(monkeypatch, tmp_path):
    from varuna_model_pipeline.sources import glorys_live

    monkeypatch.setitem(sys.modules, "copernicusmarine", None)

    with pytest.raises(ImportError, match="copernicusmarine is not installed"):
        glorys_live.fetch_live_glorys_window(output_dir=tmp_path)
