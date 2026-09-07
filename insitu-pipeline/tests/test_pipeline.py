"""
Test end-to-end pipeline execution and profile grouping.
"""

from varuna_insitu_pipeline.pipeline import InSituPipeline
from varuna_insitu_pipeline.schemas import RegionBounds


def test_pipeline_run_local_demo():
    pipeline = InSituPipeline()
    bounds = RegionBounds(lat_min=5.0, lat_max=25.0, lon_min=80.0, lon_max=100.0)

    snapshot, profiles, qc_report = pipeline.run(bounds=bounds, source="local_demo")

    assert snapshot.region == "bay_of_bengal"
    assert snapshot.source == "local_demo"
    assert len(snapshot.points) > 0

    # Ensure each surface snapshot point has non-negative depth and is valid
    for pt in snapshot.points:
        assert pt.depth_m <= 10.0  # surface snapshot
        assert 5.0 <= pt.lat <= 25.0
        assert 80.0 <= pt.lon <= 100.0
        assert pt.sst_c is not None

    # Ensure profiles exist for deep sensors
    assert len(profiles) > 0
    argo_profiles = [p for p in profiles if p.sensor_type.value == "argo"]
    assert len(argo_profiles) > 0
    # An Argo profile should have multiple depth levels
    assert len(argo_profiles[0].levels) > 1

    # QC report
    assert qc_report.retained_records > 0
    assert qc_report.execution_time_ms >= 0.0


def test_pipeline_get_snapshot_convenience():
    pipeline = InSituPipeline()
    snapshot = pipeline.get_snapshot()
    assert snapshot.region == "bay_of_bengal"
    assert len(snapshot.points) > 0
