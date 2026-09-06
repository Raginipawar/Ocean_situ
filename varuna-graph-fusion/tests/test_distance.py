import math

from graph_fusion.distance import bearing_vector, connectivity_weight, current_alignment, haversine_km


def test_haversine_zero_distance():
    assert haversine_km(13.0, 88.0, 13.0, 88.0) == 0.0


def test_haversine_known_one_degree_latitude():
    # ~111.19 km per degree of latitude near the equator
    d = haversine_km(0.0, 80.0, 1.0, 80.0)
    assert 110.5 < d < 111.5


def test_bearing_vector_is_unit_length():
    bx, by = bearing_vector(13.0, 88.0, 14.0, 89.0)
    assert math.isclose(math.hypot(bx, by), 1.0, rel_tol=1e-6)


def test_current_alignment_bounds():
    bearing = (1.0, 0.0)  # due east
    assert math.isclose(current_alignment(bearing, u=1.0, v=0.0), 1.0, rel_tol=1e-6)
    assert math.isclose(current_alignment(bearing, u=-1.0, v=0.0), -1.0, rel_tol=1e-6)
    assert math.isclose(current_alignment(bearing, u=0.0, v=1.0), 0.0, abs_tol=1e-6)
    assert current_alignment(bearing, u=0.0, v=0.0) == 0.0


def test_connectivity_weight_decays_with_distance():
    near = connectivity_weight(
        13.0, 88.0, 0.0, 13.1, 88.1, 0.0,
        mean_current_u=0.0, mean_current_v=0.0,
        length_scale_km=150.0, depth_scale_m=200.0, base_flow_weight=0.4,
    )
    far = connectivity_weight(
        13.0, 88.0, 0.0, 18.0, 95.0, 0.0,
        mean_current_u=0.0, mean_current_v=0.0,
        length_scale_km=150.0, depth_scale_m=200.0, base_flow_weight=0.4,
    )
    assert 0.0 < far.weight < near.weight <= 1.0


def test_connectivity_weight_decays_with_depth_difference():
    shallow_pair = connectivity_weight(
        13.0, 88.0, 0.0, 13.1, 88.1, 0.0,
        mean_current_u=0.0, mean_current_v=0.0,
        length_scale_km=150.0, depth_scale_m=200.0, base_flow_weight=0.4,
    )
    deep_pair = connectivity_weight(
        13.0, 88.0, 0.0, 13.1, 88.1, 1000.0,
        mean_current_u=0.0, mean_current_v=0.0,
        length_scale_km=150.0, depth_scale_m=200.0, base_flow_weight=0.4,
    )
    assert deep_pair.weight < shallow_pair.weight


def test_connectivity_weight_boosted_by_flow_alignment():
    # Same two points, same distance -- only the ambient current direction changes.
    aligned = connectivity_weight(
        13.0, 88.0, 0.0, 13.0, 89.0, 0.0,  # due east of point 1
        mean_current_u=1.0, mean_current_v=0.0,  # current flowing east -> aligned
        length_scale_km=150.0, depth_scale_m=200.0, base_flow_weight=0.4,
    )
    perpendicular = connectivity_weight(
        13.0, 88.0, 0.0, 13.0, 89.0, 0.0,
        mean_current_u=0.0, mean_current_v=1.0,  # current flowing north -> perpendicular
        length_scale_km=150.0, depth_scale_m=200.0, base_flow_weight=0.4,
    )
    opposed = connectivity_weight(
        13.0, 88.0, 0.0, 13.0, 89.0, 0.0,
        mean_current_u=-1.0, mean_current_v=0.0,  # current flowing west -> opposed
        length_scale_km=150.0, depth_scale_m=200.0, base_flow_weight=0.4,
    )
    assert aligned.weight > perpendicular.weight > opposed.weight
