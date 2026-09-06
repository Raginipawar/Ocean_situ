"""
VARUNA Backend — OGC map tile renderer.

Server-side rendering of ocean variable maps for WMS GetMap responses.
Takes fused data points, interpolates them onto a regular grid within
the requested bounding box, and renders a colormapped PNG image.

Uses matplotlib (non-interactive Agg backend) and scipy for interpolation.
"""
from __future__ import annotations

import io
import logging
from typing import Any

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for server-side rendering

import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import griddata

logger = logging.getLogger("varuna.ogc_renderer")

# Layer definitions: field name → (colormap, label, vmin, vmax)
LAYER_CONFIGS: dict[str, tuple[str, str, float, float]] = {
    "sst": ("RdYlBu_r", "Sea Surface Temperature (°C)", 20.0, 34.0),
    "trust": ("RdYlGn", "Trust Score", 0.0, 1.0),
    "currents": ("cividis", "Current Speed (m/s)", 0.0, 1.5),
    "wave_height": ("YlOrRd", "Wave Height (m)", 0.0, 4.0),
    "current_u": ("coolwarm", "Zonal Current (m/s)", -1.0, 1.0),
    "current_v": ("coolwarm", "Meridional Current (m/s)", -1.0, 1.0),
}


def _extract_layer_values(
    points: list[dict],
    layer: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Extract lat, lon, and value arrays from fused data points for a given layer.

    Returns (lats, lons, values) with NaN-filtered entries.
    """
    lats, lons, vals = [], [], []

    for pt in points:
        lat = pt.get("lat")
        lon = pt.get("lon")
        if lat is None or lon is None:
            continue

        if layer == "sst":
            v = pt.get("sst_c")
        elif layer == "trust":
            v = pt.get("confidence", pt.get("trust_score"))
        elif layer == "currents":
            u = pt.get("current_u_ms")
            vv = pt.get("current_v_ms")
            v = np.sqrt(u**2 + vv**2) if u is not None and vv is not None else None
        elif layer == "wave_height":
            v = pt.get("wave_height_m")
        elif layer == "current_u":
            v = pt.get("current_u_ms")
        elif layer == "current_v":
            v = pt.get("current_v_ms")
        else:
            v = None

        if v is not None and np.isfinite(v):
            lats.append(lat)
            lons.append(lon)
            vals.append(v)

    return np.array(lats), np.array(lons), np.array(vals)


def render_map_tile(
    points: list[dict],
    layer: str,
    bbox: tuple[float, float, float, float],
    width: int = 512,
    height: int = 512,
) -> bytes:
    """
    Render a colormapped map tile as PNG bytes.

    Parameters
    ----------
    points : list[dict]
        Fused data points (from /fused endpoint).
    layer : str
        Layer name: sst, trust, currents, wave_height, current_u, current_v.
    bbox : tuple
        (lon_min, lat_min, lon_max, lat_max) in EPSG:4326.
    width, height : int
        Output image dimensions in pixels.

    Returns
    -------
    bytes
        PNG image data.
    """
    if layer not in LAYER_CONFIGS:
        raise ValueError(f"Unknown layer: {layer}. Available: {list(LAYER_CONFIGS.keys())}")

    cmap_name, label, vmin, vmax = LAYER_CONFIGS[layer]
    lon_min, lat_min, lon_max, lat_max = bbox

    lats, lons, vals = _extract_layer_values(points, layer)

    if len(vals) < 3:
        # Not enough data points — render a blank tile with a message
        return _render_blank_tile(width, height, f"Insufficient data for {layer}")

    # Filter points within the bounding box (with small margin)
    margin = 1.0
    mask = (
        (lats >= lat_min - margin) & (lats <= lat_max + margin) &
        (lons >= lon_min - margin) & (lons <= lon_max + margin)
    )
    lats, lons, vals = lats[mask], lons[mask], vals[mask]

    if len(vals) < 3:
        return _render_blank_tile(width, height, f"No data in bbox for {layer}")

    # Create interpolation grid
    grid_x = np.linspace(lon_min, lon_max, width)
    grid_y = np.linspace(lat_min, lat_max, height)
    grid_lon, grid_lat = np.meshgrid(grid_x, grid_y)

    try:
        grid_vals = griddata(
            (lons, lats), vals,
            (grid_lon, grid_lat),
            method="cubic",
            fill_value=np.nan,
        )
    except Exception:
        # Fall back to linear interpolation
        grid_vals = griddata(
            (lons, lats), vals,
            (grid_lon, grid_lat),
            method="linear",
            fill_value=np.nan,
        )

    # Render with matplotlib
    dpi = 100
    fig_w = width / dpi
    fig_h = height / dpi
    fig, ax = plt.subplots(1, 1, figsize=(fig_w, fig_h), dpi=dpi)

    ax.set_xlim(lon_min, lon_max)
    ax.set_ylim(lat_min, lat_max)
    ax.set_aspect("auto")

    im = ax.pcolormesh(
        grid_lon, grid_lat, grid_vals,
        cmap=cmap_name, vmin=vmin, vmax=vmax,
        shading="auto",
    )

    # Remove all axes decoration for a clean tile
    ax.axis("off")
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)

    # Render to PNG bytes
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0, transparent=True)
    plt.close(fig)
    buf.seek(0)

    return buf.read()


def _render_blank_tile(width: int, height: int, message: str) -> bytes:
    """Render a blank tile with a centered message."""
    dpi = 100
    fig, ax = plt.subplots(1, 1, figsize=(width / dpi, height / dpi), dpi=dpi)
    ax.text(
        0.5, 0.5, message,
        ha="center", va="center",
        fontsize=12, color="gray",
        transform=ax.transAxes,
    )
    ax.axis("off")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0, transparent=True)
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def get_available_layers() -> list[dict]:
    """Return metadata about available WMS layers."""
    return [
        {
            "name": name,
            "colormap": cmap,
            "label": label,
            "value_range": [vmin, vmax],
        }
        for name, (cmap, label, vmin, vmax) in LAYER_CONFIGS.items()
    ]
