import numpy as np
import pytest

from streaming_nowcast import grid_utils, real_data
from streaming_nowcast.schemas import ModelGridPoint, ModelSnapshot


def test_points_to_grid_places_values_at_nearest_cell():
    target_lat, target_lon = real_data.target_grid_axes()
    points = [
        ModelGridPoint(lat=float(target_lat[2]), lon=float(target_lon[3]), sst_c=29.5),
    ]
    snapshot = ModelSnapshot(region="bay_of_bengal", resolution_deg=1.0, points=points)

    grid = grid_utils.points_to_grid(snapshot, "sst_c")

    assert grid.shape == (target_lat.size, target_lon.size)
    assert grid[2, 3] == pytest.approx(29.5)
    assert np.isnan(grid[0, 0])  # untouched cells are NaN, not 0


def test_points_to_grid_skips_none_values():
    target_lat, target_lon = real_data.target_grid_axes()
    points = [ModelGridPoint(lat=float(target_lat[0]), lon=float(target_lon[0]), sst_c=None)]
    snapshot = ModelSnapshot(region="bay_of_bengal", resolution_deg=1.0, points=points)

    grid = grid_utils.points_to_grid(snapshot, "sst_c")

    assert np.isnan(grid[0, 0])


def test_grid_to_nowcast_snapshot_round_trip_count():
    target_lat, target_lon = real_data.target_grid_axes()
    grid = np.full((target_lat.size, target_lon.size), 28.0)

    snapshot = grid_utils.grid_to_nowcast_snapshot(grid, "bay_of_bengal", 1.0, lead_time_s=3600)

    assert len(snapshot.points) == target_lat.size * target_lon.size
    assert snapshot.status == "working"


def test_grid_to_nowcast_snapshot_rejects_wrong_shape():
    with pytest.raises(ValueError):
        grid_utils.grid_to_nowcast_snapshot(np.zeros((3, 3)), "bay_of_bengal", 1.0, lead_time_s=1.0)
