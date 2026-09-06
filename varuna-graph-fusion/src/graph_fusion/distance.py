"""
Oceanographic connectivity weighting.

This is the answer to the hardest question judges will ask: "how is this
different from just interpolating by distance?"

Two points that are close in raw lat/lon can be poorly connected in the real
ocean (e.g. sitting across a strong current front or at very different
depths), while two points further apart but sitting along the same current
can exchange water mass properties quickly. So an edge's weight here is a
product of three independent factors:

  1. spatial_decay   - closer points get more weight (Gaussian-ish decay)
  2. depth_decay     - points at similar depth get more weight (stratification
                        limits vertical mixing)
  3. flow_factor     - points that lie along the local current direction get
                        boosted weight; points across-current get damped,
                        even at the same distance

Only step 1 is "distance-based interpolation". Steps 2 and 3 are what make
this a *graph* fusion engine grounded in ocean physics rather than an IDW
(inverse-distance-weighting) scheme with extra steps.

KD-tree candidate search (in graph_builder.py) is a separate, purely
computational concern: it is only used to keep the graph sparse as the sensor
network grows (avoiding an O(n^2) fully-connected graph), not to decide how
strongly two points influence each other.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points, in kilometres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c


def bearing_vector(lat1: float, lon1: float, lat2: float, lon2: float) -> tuple[float, float]:
    """
    Unit vector (east_component, north_component) pointing from point 1 to
    point 2, in a local tangent-plane approximation. Good enough at the
    regional (Bay of Bengal) scale this engine operates at.
    """
    lat_scale = 111.32  # km per degree latitude
    lon_scale = 111.32 * math.cos(math.radians((lat1 + lat2) / 2.0))

    dx = (lon2 - lon1) * lon_scale  # east-west, km
    dy = (lat2 - lat1) * lat_scale  # north-south, km
    norm = math.hypot(dx, dy)
    if norm < 1e-9:
        return (0.0, 0.0)
    return (dx / norm, dy / norm)


def current_alignment(bearing: tuple[float, float], u: float, v: float) -> float:
    """
    Cosine similarity in [-1, 1] between the direction from point A to point B
    and the local current vector (u = eastward m/s, v = northward m/s).

    +1 -> the current flows directly from A towards B (strongly connected)
     0 -> the current is perpendicular to the A-B line (no advective link)
    -1 -> the current flows directly away from B (weakly connected)
    """
    speed = math.hypot(u, v)
    if speed < 1e-6:
        return 0.0
    bx, by = bearing
    return (bx * u + by * v) / speed


@dataclass(frozen=True)
class ConnectivityWeight:
    weight: float
    distance_km: float
    depth_diff_m: float
    flow_factor: float  # 0..1, 1 = fully current-aligned


def connectivity_weight(
    lat1: float,
    lon1: float,
    depth1_m: float,
    lat2: float,
    lon2: float,
    depth2_m: float,
    mean_current_u: float,
    mean_current_v: float,
    length_scale_km: float,
    depth_scale_m: float,
    base_flow_weight: float,
) -> ConnectivityWeight:
    """
    Oceanographic connectivity weight between two nodes, in (0, 1].

    `mean_current_u/v` should be the current at the midpoint between the two
    nodes (or the average of both nodes' local currents) -- whatever the
    caller has available from the model background field.
    """
    dist_km = haversine_km(lat1, lon1, lat2, lon2)
    spatial_decay = math.exp(-dist_km / length_scale_km)

    depth_diff_m = abs(depth1_m - depth2_m)
    depth_decay = math.exp(-depth_diff_m / depth_scale_m)

    bearing = bearing_vector(lat1, lon1, lat2, lon2)
    alignment = current_alignment(bearing, mean_current_u, mean_current_v)  # -1..1
    flow_factor = 0.5 * (1.0 + alignment)  # 0..1

    flow_multiplier = base_flow_weight + (1.0 - base_flow_weight) * flow_factor

    weight = spatial_decay * depth_decay * flow_multiplier
    return ConnectivityWeight(
        weight=weight,
        distance_km=dist_km,
        depth_diff_m=depth_diff_m,
        flow_factor=flow_factor,
    )
