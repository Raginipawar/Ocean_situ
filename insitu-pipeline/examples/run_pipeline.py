"""
Example: Running the VARUNA In-Situ Pipeline.

Demonstrates:
1. Ingesting in-situ observation data across active adapters.
2. Inspecting the canonical ObservationSnapshot (Person 1 / Person 5 contract).
3. Inspecting depth-stratified vertical profiles (Argo/Glider).
4. Reviewing the Quality Control & Sanitization Report.
"""
import json
from varuna_insitu_pipeline import InSituPipeline, RegionBounds


def main():
    print("Initializing VARUNA In-Situ Observation Pipeline...")
    pipeline = InSituPipeline()

    # Define Bay of Bengal bounding box
    bounds = RegionBounds(lat_min=5.0, lat_max=25.0, lon_min=80.0, lon_max=100.0)

    # Execute end-to-end pipeline run
    snapshot, profiles, qc = pipeline.run(bounds=bounds, source="local_demo")

    print("\n========================================================")
    print(f"1. CANONICAL OBSERVATIONS SNAPSHOT (/observations contract)")
    print("========================================================")
    print(f"Region:          {snapshot.region}")
    print(f"Source:          {snapshot.source}")
    print(f"Timestamp:       {snapshot.time.isoformat()}")
    print(f"Surface Sensors: {len(snapshot.points)}")

    print("\nFirst 5 Surface Observations:")
    for pt in snapshot.points[:5]:
        print(f"  [{pt.sensor_type.value.upper():7s}] {pt.sensor_id:18s} @ ({pt.lat:5.2f}N, {pt.lon:5.2f}E) | "
              f"SST: {pt.sst_c:4.1f}C | Salinity: {pt.salinity_psu or 0.0:4.1f} PSU | Waves: {pt.wave_height_m or 0.0:3.1f}m")

    print("\n========================================================")
    print(f"2. 3D VERTICAL PROFILES (For 3D Inspection / Depth Slices)")
    print("========================================================")
    print(f"Total Profiles:  {len(profiles)}")
    if profiles:
        p0 = profiles[0]
        print(f"Sample Profile:  {p0.sensor_id} ({p0.sensor_type.value}) @ ({p0.lat}N, {p0.lon}E)")
        for lev in p0.levels[:4]:
            print(f"  Depth {lev.depth_m:5.1f}m -> Temp: {lev.temperature_c}C, Sal: {lev.salinity_psu} PSU")

    print("\n========================================================")
    print(f"3. QUALITY CONTROL & SANITIZATION REPORT")
    print("========================================================")
    print(f"Total Raw Records Processed: {qc.total_raw_records}")
    print(f"Retained Valid Records:      {qc.retained_records}")
    print(f"Dropped Out-of-Bounds:       {qc.dropped_out_of_bounds}")
    print(f"Dropped Bad QC Flags:        {qc.dropped_bad_qc}")
    print(f"Dropped Sentinels / NaN:     {qc.dropped_sentinels}")
    print(f"Execution Latency:           {qc.execution_time_ms:.2f} ms")


if __name__ == "__main__":
    main()
