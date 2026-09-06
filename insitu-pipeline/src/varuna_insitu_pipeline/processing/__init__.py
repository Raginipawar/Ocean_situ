"""
Data processing, sanitization, and quality control modules.
"""
from .depth import build_vertical_profiles, extract_surface_snapshot
from .qc import is_qc_acceptable, parse_qc_flag
from .sanitize import PHYSICAL_LIMITS, SENTINEL_VALUES, clean_measurement, is_sentinel
from .spatial import (
    haversine_distance_km,
    is_in_bounds,
    normalize_longitude,
    validate_coordinates,
)

__all__ = [
    "PHYSICAL_LIMITS",
    "SENTINEL_VALUES",
    "build_vertical_profiles",
    "clean_measurement",
    "extract_surface_snapshot",
    "haversine_distance_km",
    "is_in_bounds",
    "is_qc_acceptable",
    "is_sentinel",
    "normalize_longitude",
    "parse_qc_flag",
    "validate_coordinates",
]
