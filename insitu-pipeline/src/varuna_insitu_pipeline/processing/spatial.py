"""
Spatial normalization and bounding box validation for ocean coordinates.
"""
from __future__ import annotations

import math

from ..schemas import RegionBounds


def normalize_longitude(lon: float) -> float:
    """
    Normalize longitude to standard [-180.0, 180.0] degrees east convention.
    Converts 0..360 system (common in some model/satellite outputs) to -180..180.
    """
    normalized = (lon + 180.0) % 360.0 - 180.0
    # Handle edge case where normalized is -180.0 vs 180.0
    if normalized == -180.0 and lon > 0:
        return 180.0
    return round(normalized, 5)


def validate_coordinates(lat: float, lon: float) -> tuple[float, float] | None:
    """
    Validate and normalize coordinates.
    Returns (normalized_lat, normalized_lon) or None if physically invalid.
    """
    try:
        lat = float(lat)
        lon = float(lon)
    except (ValueError, TypeError):
        return None

    if math.isnan(lat) or math.isnan(lon) or math.isinf(lat) or math.isinf(lon):
        return None

    if not (-90.0 <= lat <= 90.0):
        return None

    norm_lon = normalize_longitude(lon)
    norm_lat = round(lat, 5)
    return norm_lat, norm_lon


def is_in_bounds(lat: float, lon: float, bounds: RegionBounds) -> bool:
    """Check if lat and lon are inside the region bounds."""
    coords = validate_coordinates(lat, lon)
    if coords is None:
        return False
    v_lat, v_lon = coords
    return bounds.contains(v_lat, v_lon)


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two points in kilometers."""
    r = 6371.0  # Earth's radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c
