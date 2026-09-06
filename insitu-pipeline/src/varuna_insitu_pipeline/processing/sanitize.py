"""
Sentinel cleaning and physical range sanitization for ocean observations.

Prevents invalid sentinels (-999, -9999, 1e35, NaN) or physically impossible
values from corrupting downstream graph fusion or drift scoring engines.
"""
from __future__ import annotations

import math

# Physical limits based on realistic oceanographic bounds
PHYSICAL_LIMITS = {
    "sst_c": (-2.0, 40.0),            # Degrees Celsius (-2C for freezing seawater up to 40C extreme tropical surface)
    "salinity_psu": (0.0, 45.0),       # Practical Salinity Units (0 for river mouths, 45 for hypersaline basins)
    "current_u_ms": (-5.0, 5.0),       # Eastward velocity m/s
    "current_v_ms": (-5.0, 5.0),       # Northward velocity m/s
    "wave_height_m": (0.0, 25.0),      # Significant wave height in meters
    "chlorophyll_mg_m3": (0.0, 50.0),  # Chlorophyll-a concentration in mg/m^3
    "depth_m": (0.0, 12000.0),         # Water depth in meters
}

# Common missing value sentinels across NetCDF, ASCII, and sensor streams
SENTINEL_VALUES = {
    -999.0,
    -9999.0,
    -99999.0,
    999.0,
    9999.0,
    99999.0,
    1e35,
    1e36,
    -1e35,
    -1e36,
}


def is_sentinel(val: float) -> bool:
    """Check if value is a known missing-data sentinel."""
    if math.isnan(val) or math.isinf(val):
        return True
    # Approximate floating point match for common sentinels
    for s in SENTINEL_VALUES:
        if abs(val - s) < 1e-4 or abs(val / (s + 1e-9) - 1.0) < 1e-4:
            return True
    return False


def clean_measurement(
    val: float | None,
    var_name: str,
    enforce_limits: bool = True,
) -> float | None:
    """
    Clean and validate a single scalar measurement.
    Maps sentinels and NaN to None.
    If enforce_limits is True, values outside physical limits are mapped to None.
    """
    if val is None:
        return None
    try:
        f_val = float(val)
    except (ValueError, TypeError):
        return None

    if math.isnan(f_val) or is_sentinel(f_val):
        return None

    if enforce_limits and var_name in PHYSICAL_LIMITS:
        min_v, max_v = PHYSICAL_LIMITS[var_name]
        if f_val < min_v or f_val > max_v:
            return None

    return round(f_val, 4)
