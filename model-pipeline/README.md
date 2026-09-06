# VARUNA Ocean Model Data Pipeline

Checkpoint 7 status: configuration, canonical schema documentation, validation
models, INCOIS LAS ingestion, GLORYS fallback ingestion, explicit source
selection/fallback behavior, Bay of Bengal region extraction, variable/unit
normalization, data-quality validation, common target grid generation,
regridding, end-to-end pipeline orchestration, deterministic local demo source,
example configuration, example metadata, usage examples, and unit tests are
implemented.

## Responsibility

This component owns only the ocean model data side of VARUNA:

1. Select the configured model source.
2. Validate incoming gridded scientific data.
3. Normalize model variables into a canonical schema.
4. Extract the Bay of Bengal demo region.
5. Regrid onto a common target grid.
6. Serialize model output for the existing `/model` integration contract.

Graph Fusion, Drift Memory, observations, APIs, WebSockets, and frontend work
remain outside this package.

## Sources

The pipeline distinguishes source provenance explicitly:

- `INCOIS_LAS`: primary source.
- `COPERNICUS_GLORYS`: configured fallback source.
- `LOCAL_DEMO`: deterministic offline/demo source.

No code should silently switch sources. Fallback behavior will be implemented in
a later checkpoint with explicit provenance metadata.

## Canonical Dataset Schema

The canonical in-memory scientific representation is an `xarray.Dataset` with:

- Coordinates:
  - `time`: timestamp coordinate, timezone-normalized before API handoff.
  - `lat`: latitude in degrees north, ascending preferred after normalization.
  - `lon`: longitude in degrees east, normalized to the configured convention.
  - `depth`: optional depth in meters for variables that preserve depth.
- Data variables:
  - `sst`: sea surface temperature, units `degC`.
  - `u_current`: eastward sea water velocity, units `m s-1`.
  - `v_current`: northward sea water velocity, units `m s-1`.
  - `wave_height`: significant wave height, units `m`.
  - `salinity`: practical salinity, units `1e-3`.
  - `chlorophyll`: chlorophyll-a concentration, units `mg m-3`.
- Dataset attrs:
  - `source`
  - `source_url`
  - `region`
  - `processing_level`
  - `target_resolution_deg`
  - `history`

Checkpoint 1 validates the schema definition and dataset metadata shape. Actual
NetCDF/xarray ingestion and regridding are intentionally left for later
checkpoints.

## Existing `/model` Compatibility

The current Graph Fusion `/model` contract accepts:

- `region`
- `time`
- `resolution_deg`
- `source`
- `points[]`
  - `lat`
  - `lon`
  - `depth_m`
  - `sst_c`
  - `current_u_ms`
  - `current_v_ms`
  - `wave_height_m`

The existing contract does not yet include salinity or chlorophyll. This
pipeline keeps those as canonical scientific variables, but a downstream schema
extension must be approved before adding them to API payloads consumed by other
team members.

## INCOIS LAS Ingestion

Implemented in `src/varuna_model_pipeline/sources/incois_las.py`.

The ingestor:

1. Opens an xarray-readable local path or URL.
2. Detects `time`, `lat`, `lon`, and optional `depth` coordinates from explicit
   supported coordinate names.
3. Resolves source variables through an explicit INCOIS LAS mapping.
4. Validates required variables are present.
5. Validates units are supported and not ambiguous.
6. Renames variables into the canonical schema.
7. Preserves source metadata and adds VARUNA provenance attributes.

It intentionally does not do region extraction, unit conversion, missing-data
quality policy, or regridding yet. Those are later checkpoints.

## GLORYS Fallback

Implemented in `src/varuna_model_pipeline/sources/glorys.py` and
`src/varuna_model_pipeline/source_selection.py`.

The GLORYS ingestor returns the same canonical Dataset schema as the INCOIS
ingestor. Source-specific variable names such as `thetao`, `uo`, `vo`, `VHM0`,
`so`, and `chl` are mapped explicitly.

Fallback behavior is explicit:

1. Try INCOIS LAS.
2. If INCOIS fails with a typed ingestion error, record the failure.
3. Try GLORYS.
4. Return the selected source plus a list of attempts for provenance.
5. If both fail, raise a clear error.

The rest of the pipeline should use the canonical Dataset and selected-source
metadata, not source-specific variable names.

## Region Extraction

Implemented in `src/varuna_model_pipeline/processing/region.py`.

The region extractor:

1. Uses configurable `RegionBounds`, defaulting to Bay of Bengal.
2. Requires real `lat` and `lon` coordinates.
3. Handles ascending and descending source coordinates.
4. Normalizes 0..360 longitude coordinates to -180..180 when needed.
5. Includes boundary coordinate points.
6. Fails clearly if the requested region contains no data.
7. Preserves dataset variables and appends region/provenance attrs.

It intentionally does not perform variable normalization, unit conversion,
missing-data filtering, or regridding. Those are later checkpoints.

## Variable, Unit, And Quality Normalization

Implemented in:

- `src/varuna_model_pipeline/processing/units.py`
- `src/varuna_model_pipeline/processing/quality.py`
- `src/varuna_model_pipeline/processing/normalize.py`

The normalization layer:

1. Requires all canonical variables unless a caller explicitly narrows the set.
2. Converts only explicit, scientifically direct units:
   - SST Kelvin to degC.
   - current cm/s to m s-1.
   - wave height cm to m.
   - accepted salinity and chlorophyll aliases to canonical metadata.
3. Rejects unsupported or ambiguous units instead of guessing.
4. Checks NaN, Inf, impossible physical values, duplicate coordinates, malformed
   timestamps, missing variables, and invalid canonical units.
5. Returns a quality report and raises on error-level issues.

This checkpoint does not fill missing values or regrid data. NaN values below
the configured threshold are reported as warnings so later stages can preserve
scientific missingness instead of fabricating data.

## Common Grid And Regridding

Implemented in:

- `src/varuna_model_pipeline/processing/grid.py`
- `src/varuna_model_pipeline/processing/regrid.py`

The common-grid layer:

1. Builds a deterministic target `lat`/`lon` grid from configured region bounds
   and spatial resolution.
2. Uses boundary-inclusive coordinate generation.
3. Regrids canonical variables with xarray interpolation over `lat` and `lon`.
4. Supports configured `linear` or `nearest` interpolation.
5. Preserves `time`, optional `depth`, variable metadata, and dataset attrs.
6. Sorts descending spatial coordinates before interpolation.
7. Preserves NaNs instead of silently filling or fabricating values.
8. Validates output coordinate alignment and variable structure.

The default target grid remains Bay of Bengal at 1.0 degree resolution.

## End-To-End Pipeline

Implemented in `src/varuna_model_pipeline/pipeline.py`.

The main entry points are:

- `load_model_data(...)`
- `process_model_data(...)`
- `prepare_model_dataset(...)`
- `load_local_demo_model_data(...)`

The composed processing path is:

```text
SOURCE
-> VALIDATE / MAP during source ingestion
-> EXTRACT BAY OF BENGAL
-> NORMALIZE UNITS
-> QUALITY CHECK
-> REGRID TO COMMON TARGET GRID
-> CANONICAL DATASET
```

Local demo execution:

```powershell
$env:PYTHONPATH='model-pipeline\src'
C:\Users\risha\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe model-pipeline\examples\run_pipeline.py
```

Example:

```powershell
$env:PYTHONPATH='model-pipeline\src'
C:\Users\risha\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe model-pipeline\examples\incois_las_usage.py path\to\incois.nc
```

## Run Tests

From the repo root:

```powershell
C:\Users\risha\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest model-pipeline\tests -q
```
