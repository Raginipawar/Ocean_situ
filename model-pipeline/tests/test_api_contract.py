"""Tests for the Checkpoint 8 API Integration Contract."""

from datetime import datetime, timezone
import math

import numpy as np
import pytest
import xarray as xr

from varuna_model_pipeline.api_contract import to_model_snapshot, ModelSnapshot


@pytest.fixture
def dummy_dataset() -> xr.Dataset:
    """Create a minimal xarray dataset that mimics a canonical dataset."""
    times = [np.datetime64("2026-09-06T12:00:00")]
    lats = [10.0, 11.0]
    lons = [80.0, 81.0]

    # Create dummy data matrices (1 time x 2 lats x 2 lons)
    sst_data = np.array([[[28.5, np.nan], [29.1, 29.2]]])
    u_data = np.array([[[0.1, 0.2], [np.nan, 0.4]]])
    
    # Missing variables like wave_height should be handled gracefully

    ds = xr.Dataset(
        data_vars=dict(
            sst=(["time", "lat", "lon"], sst_data),
            u_current=(["time", "lat", "lon"], u_data),
        ),
        coords=dict(
            time=times,
            lat=lats,
            lon=lons,
        ),
        attrs=dict(
            region="bay_of_bengal",
            source="LOCAL_DEMO",
            target_resolution_deg=1.0,
        ),
    )
    return ds


def test_to_model_snapshot_schema_validity(dummy_dataset: xr.Dataset):
    """Test that the converted dataset strictly adheres to the ModelSnapshot Pydantic schema."""
    
    snapshot = to_model_snapshot(dummy_dataset)
    
    assert isinstance(snapshot, ModelSnapshot)
    assert snapshot.region == "bay_of_bengal"
    assert snapshot.source == "LOCAL_DEMO"
    assert snapshot.resolution_deg == 1.0
    
    # Check time was parsed correctly
    assert snapshot.time.year == 2026
    assert snapshot.time.month == 9
    assert snapshot.time.day == 6
    assert snapshot.time.hour == 12
    assert snapshot.time.tzinfo == timezone.utc
    
    # 2 lats * 2 lons = 4 points
    assert len(snapshot.points) == 4
    
    # Validate a specific point
    pt_10_80 = next(p for p in snapshot.points if p.lat == 10.0 and p.lon == 80.0)
    assert pt_10_80.sst_c == 28.5
    assert pt_10_80.current_u_ms == 0.1
    assert pt_10_80.current_v_ms is None
    assert pt_10_80.wave_height_m is None
    
    # Validate NaN handling
    pt_10_81 = next(p for p in snapshot.points if p.lat == 10.0 and p.lon == 81.0)
    assert pt_10_81.sst_c is None  # np.nan converted to None
    assert pt_10_81.current_u_ms == 0.2
