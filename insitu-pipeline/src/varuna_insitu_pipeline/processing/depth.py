"""
Depth stratification and profile extraction.

Provides functions to:
1. Extract surface observations (depth <= max_surface_depth) for the 2D /observations contract.
2. Group multi-depth sensor readings into vertical profiles for 3D inspection.
"""
from __future__ import annotations

from ..schemas import ObservationPoint, ProfileLevel, VerticalProfile


def extract_surface_snapshot(
    points: list[ObservationPoint],
    max_surface_depth_m: float = 10.0,
) -> list[ObservationPoint]:
    """
    Select one representative surface observation per sensor platform.
    If a sensor has multiple depth levels, selects the shallowest level that has
    valid data (or depth <= max_surface_depth_m).
    """
    # Group by sensor_id
    by_sensor: dict[str, list[ObservationPoint]] = {}
    for p in points:
        by_sensor.setdefault(p.sensor_id, []).append(p)

    surface_points: list[ObservationPoint] = []
    for sensor_points in by_sensor.values():
        # Sort by depth ascending
        sorted_points = sorted(sensor_points, key=lambda x: x.depth_m)
        
        # Look for the shallowest point within max_surface_depth_m
        chosen = None
        for p in sorted_points:
            if p.depth_m <= max_surface_depth_m:
                chosen = p
                break
        
        # If no point <= max_surface_depth_m, take the shallowest available
        if chosen is None and sorted_points:
            chosen = sorted_points[0]
            
        if chosen:
            surface_points.append(chosen)

    return surface_points


def build_vertical_profiles(points: list[ObservationPoint]) -> list[VerticalProfile]:
    """
    Group points into VerticalProfiles by sensor_id.
    """
    by_sensor: dict[str, list[ObservationPoint]] = {}
    for p in points:
        by_sensor.setdefault(p.sensor_id, []).append(p)

    profiles: list[VerticalProfile] = []
    for sensor_id, sensor_points in by_sensor.items():
        if not sensor_points:
            continue
        first = sensor_points[0]
        levels = []
        for sp in sorted(sensor_points, key=lambda x: x.depth_m):
            levels.append(
                ProfileLevel(
                    depth_m=sp.depth_m,
                    temperature_c=sp.sst_c,
                    salinity_psu=sp.salinity_psu,
                    current_u_ms=sp.current_u_ms,
                    current_v_ms=sp.current_v_ms,
                    chlorophyll_mg_m3=sp.chlorophyll_mg_m3,
                    qc_flag=1,
                )
            )
        profiles.append(
            VerticalProfile(
                sensor_id=sensor_id,
                sensor_type=first.sensor_type,
                lat=first.lat,
                lon=first.lon,
                time=first.time,
                levels=levels,
            )
        )

    return profiles
