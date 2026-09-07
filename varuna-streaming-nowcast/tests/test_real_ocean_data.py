"""
Tests against the real Copernicus Marine files gathered for this track.

These files are large (hundreds of MB to ~1GB) and user-specific downloads,
not committed to the repo -- so every test here is skipped, not failed, if
the files aren't present at the well-known local paths used while building
this track. CI and teammates without the files still get a clean run; this
suite exists for whoever has (or re-downloads) the real data to verify the
loader against it.
"""
from pathlib import Path

import numpy as np
import pytest

from streaming_nowcast import real_ocean_data

PHY_PATH = Path(r"C:\Users\nikhi\Desktop\STUDY\TY SEM I\SIH\bay_of_bengal_phy_reanalysis.nc")
WAVE_PATH = Path(r"C:\Users\nikhi\Downloads\wave height.nc")
CHLOROPHYLL_PATH = Path(r"C:\Users\nikhi\Downloads\chlorophyll.nc")

_REAL_FILES_PRESENT = PHY_PATH.exists() and WAVE_PATH.exists() and CHLOROPHYLL_PATH.exists()

pytestmark = pytest.mark.skipif(
    not _REAL_FILES_PRESENT,
    reason="real Copernicus Marine files not present on this machine",
)


def test_load_real_training_volume_shapes_and_ranges():
    data = real_ocean_data.load_real_training_volume(PHY_PATH, WAVE_PATH, CHLOROPHYLL_PATH)

    assert set(data) == set(real_ocean_data.VARIABLES)

    expected_shape = (
        90,
        len(real_ocean_data.TARGET_DEPTH_IDX),
        real_ocean_data.TARGET_LAT.size,
        real_ocean_data.TARGET_LON.size,
    )
    for name, arr in data.items():
        assert arr.shape == expected_shape, name

    # Physically plausible real-world ranges -- catches a repeat of the
    # regrid bug found in varuna_model_pipeline (values up to ~1e280).
    assert -5 < np.nanmin(data["sst_c"]) and np.nanmax(data["sst_c"]) < 45
    assert 0 < np.nanmin(data["salinity_psu"]) and np.nanmax(data["salinity_psu"]) < 45
    assert np.nanmax(np.abs(data["current_u_ms"])) < 10
    assert np.nanmax(np.abs(data["current_v_ms"])) < 10
    assert 0 <= np.nanmin(data["wave_height_m"]) and np.nanmax(data["wave_height_m"]) < 20
    assert 0 <= np.nanmin(data["chlorophyll_mg_m3"])


def test_load_real_training_volume_has_real_land_mask():
    data = real_ocean_data.load_real_training_volume(PHY_PATH, WAVE_PATH, CHLOROPHYLL_PATH)
    nan_fraction = np.isnan(data["sst_c"]).mean()
    # Bay of Bengal box genuinely includes a lot of coastline (India,
    # Myanmar, Sri Lanka, Bangladesh) -- some meaningful land fraction is
    # expected, but not "mostly land" or "no land at all".
    assert 0.1 < nan_fraction < 0.6
