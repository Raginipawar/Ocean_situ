"""
Test sensor adapters and adapter registry.
"""

from varuna_insitu_pipeline.adapters.buoy_adapter import BuoyObservationAdapter
from varuna_insitu_pipeline.adapters.local_demo import LocalDemoObservationAdapter
from varuna_insitu_pipeline.adapters.registry import AdapterRegistry
from varuna_insitu_pipeline.schemas import RegionBounds


def test_adapter_registry():
    adapters = AdapterRegistry.list_adapters()
    assert "local_demo" in adapters
    assert "buoy" in adapters
    assert "argovis" in adapters

    # Instantiate local_demo via registry
    adapter = AdapterRegistry.instantiate("local_demo")
    assert isinstance(adapter, LocalDemoObservationAdapter)


def test_local_demo_adapter():
    adapter = LocalDemoObservationAdapter()
    bounds = RegionBounds(lat_min=5.0, lat_max=25.0, lon_min=80.0, lon_max=100.0)
    raw = adapter.fetch_raw(bounds)
    assert len(raw) > 0

    points, report = adapter.parse_and_clean(raw, bounds)
    assert len(points) > 0
    assert report.retained_records == len(points)
    assert report.dropped_bad_qc == 0

    # Ensure key Bay of Bengal stations are present
    sensor_ids = {p.sensor_id for p in points}
    assert any("niot-bd08" in sid for sid in sensor_ids)
    assert any("argo-2902698" in sid for sid in sensor_ids)


def test_buoy_csv_adapter():
    sample_csv = """sensor_id,sensor_type,lat,lon,depth_m,time,sst_c,salinity_psu,current_u_ms,current_v_ms,wave_height_m,qc_flag
bd08,buoy,18.2,89.7,0.0,2026-09-07T00:00:00Z,29.1,31.2,0.15,-0.08,1.4,1
bd09,buoy,17.5,89.2,0.0,2026-09-07T00:00:00Z,28.8,32.0,0.10,-0.05,1.2,1
bad_qc,buoy,16.0,88.0,0.0,2026-09-07T00:00:00Z,28.5,33.0,0.10,-0.05,1.0,4
out_of_bounds,buoy,35.0,88.0,0.0,2026-09-07T00:00:00Z,20.0,35.0,0.0,0.0,1.0,1
"""
    adapter = BuoyObservationAdapter()
    raw = adapter.parse_buoy_csv(sample_csv)
    assert len(raw) == 4

    bounds = RegionBounds(lat_min=5.0, lat_max=25.0, lon_min=80.0, lon_max=100.0)
    points, report = adapter.parse_and_clean(raw, bounds)
    assert len(points) == 2
    assert report.dropped_bad_qc == 1
    assert report.dropped_out_of_bounds == 1

    p_ids = [p.sensor_id for p in points]
    assert "bd08" in p_ids
    assert "bd09" in p_ids
