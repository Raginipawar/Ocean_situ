# VARUNA In-Situ Ocean Observation Data Pipeline & Extensible Adapter Pattern

**Smart India Hackathon 2026** · **Problem Statement SIH26067** (Ministry of Earth Sciences)  
**Team Hudson Hackers** · **Track:** Person 6 (In-Situ Ingestion Pipeline + Extensible Adapter Pattern)

---

## 1. Overview & Problem Context

In the VARUNA digital twin of the Indian Ocean (specifically the **Bay of Bengal**: 5°N–25°N, 80°E–100°E), there are two versions of the ocean:
- **Version A (Simulated Ocean)**: Numerical forecasts (ROMS/HOOFS/INDOFOS/GLORYS), owned by Person 4 (`/model`).
- **Version B (The Real Ocean)**: Physical measurements from autonomous floats, moorings, and ship cruises, owned by **Person 6** (`/observations`).

The in-situ data pipeline ingests, validates, quality-controls, and normalizes sparse ground-truth oceanographic observations. It directly fulfills the Problem Statement's **"Extensible Design"** criterion:
> *"Add new sensor/variable without re-engineering? Yes - adapter plugin"*

---

## 2. Key Capabilities & Architecture

```
[ External Sensor Sources ]
 ├── Ifremer FTP / Coriolis GDAC (NetCDF: Argo Floats, Gliders)
 ├── Argovis REST API (Near real-time Argo profile queries)
 ├── NOAA World Ocean Database (WOD / CTD hydrographic casts)
 ├── Moored Surface Buoy Networks (NIOT OMNI BD08-BD14, RAMA 90E)
 └── Deterministic Local Demo Dataset (Pre-cached Bay of Bengal observations)
                │
                ▼
 [ In-Situ Adapter Layer (Adapter Pattern) ]
  ├── BaseSensorAdapter (Abstract Base Class)
  │    ├── ArgoNetCDFAdapter
  │    ├── ArgovisRestAdapter
  │    ├── GliderNetCDFAdapter
  │    ├── BuoyObservationAdapter
  │    ├── NoaaWodAdapter
  │    └── LocalDemoObservationAdapter
  └── AdapterRegistry (Dynamic factory & discovery)
                │
                ▼
 [ In-Situ Processing & Quality Control Pipeline ]
  ├── QC Flag Filter (Argo QC flags 1 & 2 retained; 3, 4, 9 dropped)
  ├── Sentinel Sanitizer (-999, -9999, 1e35, NaN -> None)
  ├── Physical Plausibility Range Validator
  ├── Spatiotemporal Bounding Filter (Bay of Bengal 5-25N, 80-100E)
  └── Depth Slicer (Surface z=0 for 2D Fusion + Vertical Profiles)
                │
                ▼
 [ Canonical In-Situ Data Model ]
  ├── ObservationSnapshot (Canonical output contract for VARUNA)
  └── VerticalProfile (3D depth-resolved profile views)
                │
                ├──────────────────────────────────────┐
                ▼                                      ▼
 [ Standalone REST API / CLI ]          [ Person 5 Backend Gateway ]
  (FastAPI: /observations, /health)      (GET /observations -> Upstream)
                │                                      │
                └──────────────────┬───────────────────┘
                                   ▼
                   [ Person 1 Graph Fusion Engine ]
                    (Consumes /observations & /model -> /fused)
```

---

## 3. Extensible Adapter Pattern: Adding New Sensors

Adding support for any new sensor platform (e.g. HF-Radar or ADCP) requires zero changes to downstream consumers. Simply subclass `BaseSensorAdapter` and apply `@register_adapter`:

```python
from varuna_insitu_pipeline.adapters import BaseSensorAdapter, RawObservationRecord, register_adapter
from varuna_insitu_pipeline.schemas import RegionBounds, SensorType

@register_adapter("hf_radar")
class HFRadarAdapter(BaseSensorAdapter):
    @property
    def adapter_name(self) -> str:
        return "hf_radar"

    @property
    def supported_sensor_types(self) -> list[SensorType]:
        return [SensorType.HF_RADAR]

    def fetch_raw(self, bounds: RegionBounds, start_time=None, end_time=None) -> list[RawObservationRecord]:
        # Ingest HF radar radial vectors and return RawObservationRecord items
        ...
```

The pipeline automatically discovers and includes the new adapter at runtime.

---

## 4. Supported In-Situ Data Sources

| Source Adapter | Platform | Ingestion Protocol | Key Variables |
|---|---|---|---|
| `local_demo` | NIOT OMNI buoys, RAMA, Argo, Glider, CTD | Deterministic offline JSON / synthetic | SST, Salinity, Currents (u/v), Waves, Chlorophyll |
| `argovis` | Global Argo profiling floats | Argovis REST API (`https://argovis-api.colorado.edu`) | Temperature, Salinity, Depth (Pressure) |
| `argo_netcdf` | Coriolis GDAC / Ifremer Argo floats | NetCDF (`xarray`/`netCDF4`) | JULD, TEMP, PSAL, QC flags |
| `buoy` | NIOT OMNI (BD08–BD14), RAMA moorings | CSV / NetCDF tabular feeds | SST, Salinity, Current vectors, Wave height |
| `noaa_wod` | World Ocean Database casts | ASCII / JSON / NetCDF | Temperature, Salinity, Depth |
| `glider_netcdf`| Autonomous underwater gliders | OceanGliders EGO NetCDF | High-resolution saw-tooth profiles |

---

## 5. Quality Control & Physical Sanitization

1. **Argo Quality Control (QC)**:
   - Acceptable: `QC=1` ("Good data") and `QC=2` ("Probably good data").
   - Filtered: `QC=3` ("Potentially correctable bad data"), `QC=4` ("Bad data"), `QC=9` ("Missing value").
2. **Sentinel Filtering**:
   - Identifies and replaces common missing-value sentinels (`-999.0`, `-9999.0`, `99999.0`, `1e35`, `NaN`) with `None`.
3. **Physical Oceanographic Plausibility Limits**:
   - Sea Surface Temperature (SST): `[-2.0°C, 40.0°C]`
   - Practical Salinity: `[0.0, 45.0 PSU]`
   - Current Velocity (u/v): `[-5.0 m/s, 5.0 m/s]`
   - Significant Wave Height: `[0.0 m, 25.0 m]`
   - Chlorophyll-a: `[0.0 mg/m³, 50.0 mg/m³]`
4. **Depth Slicing**:
   - Extract surface observations (depth ≤ 10m) for the 2D surface snapshot consumed by Graph Fusion.
   - Preserves complete multi-depth profiles for 3D vertical inspection.

---

## 6. Contract Compliance with Person 1 & Person 5

The pipeline outputs JSON that strictly satisfies `graph_fusion.schemas.ObservationSnapshot`:

```json
{
  "region": "bay_of_bengal",
  "time": "2026-09-07T00:00:00Z",
  "source": "local_demo",
  "points": [
    {
      "sensor_id": "niot-bd08",
      "sensor_type": "buoy",
      "lat": 18.2,
      "lon": 89.7,
      "depth_m": 0.0,
      "time": "2026-09-07T00:00:00Z",
      "sst_c": 29.1,
      "current_u_ms": 0.15,
      "current_v_ms": -0.08,
      "wave_height_m": 1.4,
      "salinity_psu": 31.2,
      "chlorophyll_mg_m3": 0.85
    }
  ]
}
```

---

## 7. Quickstart & CLI Usage

### Installation
```powershell
cd Ocean_situ/insitu-pipeline
pip install -e .
```

### Running the Pipeline
```powershell
# Print summary of ingested Bay of Bengal observations
python -m varuna_insitu_pipeline.cli run

# List all discovered adapters
python -m varuna_insitu_pipeline.cli adapters

# Export offline deterministic dataset
python -m varuna_insitu_pipeline.cli export --out data/demo_bay_of_bengal_obs.json
```

### Launching the Standalone Microservice
```powershell
python -m varuna_insitu_pipeline.cli serve --port 8002
# Microservice running at http://localhost:8002/observations
```

### Running Example Script
```powershell
python examples/run_pipeline.py
```

### Running Tests
```powershell
pytest -v
```

---

## 8. Integration with VARUNA Ecosystem

- **Connecting to Person 1 (Graph Fusion)**:
  ```powershell
  $env:VARUNA_OBS_SOURCE = "http"
  $env:VARUNA_OBS_SOURCE_URL = "http://localhost:8002/observations"
  uvicorn graph_fusion.api:app --reload --port 8000
  ```
- **Connecting to Person 5 (Backend Gateway)**:
  ```powershell
  # Backend config
  $env:GRAPH_FUSION_URL = "http://localhost:8000"
  uvicorn app.main:app --port 8080
  # GET http://localhost:8080/observations proxies upstream observation data
  ```
