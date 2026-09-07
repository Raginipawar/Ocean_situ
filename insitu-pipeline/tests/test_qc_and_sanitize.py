"""
Test oceanographic quality control, sentinels, and physical sanitization.
"""

from varuna_insitu_pipeline.processing.qc import is_qc_acceptable, parse_qc_flag
from varuna_insitu_pipeline.processing.sanitize import clean_measurement, is_sentinel
from varuna_insitu_pipeline.processing.spatial import (
    haversine_distance_km,
    is_in_bounds,
    normalize_longitude,
    validate_coordinates,
)
from varuna_insitu_pipeline.schemas import RegionBounds


def test_qc_flag_parsing():
    assert parse_qc_flag(1) == 1
    assert parse_qc_flag("1") == 1
    assert parse_qc_flag(b"2") == 2
    assert parse_qc_flag(" 4 ") == 4
    assert parse_qc_flag(None) is None
    assert parse_qc_flag("bad") is None


def test_qc_acceptability():
    # Flags 1 (good) and 2 (probably good) should pass by default
    assert is_qc_acceptable(1) is True
    assert is_qc_acceptable("1") is True
    assert is_qc_acceptable(2) is True
    # Flags 3 (potentially correctable bad), 4 (bad), 9 (missing) should fail
    assert is_qc_acceptable(3) is False
    assert is_qc_acceptable(4) is False
    assert is_qc_acceptable(9) is False
    # None flag should be accepted as non-annotated
    assert is_qc_acceptable(None) is True


def test_sentinel_detection():
    assert is_sentinel(-999.0) is True
    assert is_sentinel(-9999.0) is True
    assert is_sentinel(1e35) is True
    assert is_sentinel(float("nan")) is True
    assert is_sentinel(float("inf")) is True
    assert is_sentinel(28.5) is False
    assert is_sentinel(0.0) is False


def test_clean_measurement_physical_limits():
    # Valid SST
    assert clean_measurement(28.4, "sst_c") == 28.4
    # Out of physical range SST (e.g. 55C or -15C)
    assert clean_measurement(55.0, "sst_c") is None
    assert clean_measurement(-15.0, "sst_c") is None
    # Sentinel SST
    assert clean_measurement(-999.0, "sst_c") is None

    # Salinity
    assert clean_measurement(33.5, "salinity_psu") == 33.5
    assert clean_measurement(100.0, "salinity_psu") is None  # impossible ocean salinity

    # Currents
    assert clean_measurement(0.45, "current_u_ms") == 0.45
    assert clean_measurement(25.0, "current_u_ms") is None  # impossible oceanic current speed


def test_spatial_normalization():
    # Longitude in 0..360 system converted to -180..180
    assert normalize_longitude(270.0) == -90.0
    assert normalize_longitude(90.0) == 90.0
    assert normalize_longitude(-45.0) == -45.0

    # Coordinate validation
    valid = validate_coordinates(15.0, 90.0)
    assert valid == (15.0, 90.0)

    # Invalid latitude
    assert validate_coordinates(120.0, 90.0) is None

    # Region bounds test
    bounds = RegionBounds(lat_min=5.0, lat_max=25.0, lon_min=80.0, lon_max=100.0)
    assert is_in_bounds(12.0, 88.0, bounds) is True
    assert is_in_bounds(35.0, 88.0, bounds) is False


def test_haversine_distance():
    # Distance between Chennai (13.08N, 80.27E) and Port Blair (11.62N, 92.73E) is approx 1360 km
    dist = haversine_distance_km(13.08, 80.27, 11.62, 92.73)
    assert 1300 < dist < 1400
