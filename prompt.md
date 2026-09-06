You are the lead backend/data engineer responsible ONLY for the OCEAN MODEL DATA PIPELINE component of the VARUNA project.

This is a national-level Smart India Hackathon project, so treat this as production-oriented scientific software, not a quick prototype. Code must be modular, testable, deterministic where possible, documented, and compatible with the rest of an existing multi-person codebase.

============================================================
1. PROJECT CONTEXT — UNDERSTAND THIS BEFORE WRITING CODE
============================================================

Project:
VARUNA — Web-based Interactive 3D Visualization Platform for Ocean Model & In-Situ Data

Core architecture:

DATA SOURCES
    ↓
INGESTION & PROCESSING
    ↓
INTELLIGENCE LAYER
    ↓
API LAYER
    ↓
3D VISUALIZATION

The complete system combines:

A. Ocean model/reanalysis data
   - My responsibility
   - Represents what the model says is happening in the ocean

B. Real in-situ observations
   - Another team member's responsibility
   - Represents what is actually being observed

C. Graph Fusion Engine
   - Another team member's responsibility
   - Combines model data and real observations

D. Drift Memory Engine
   - Another team member's responsibility
   - Detects divergence between model and reality

E. Backend API
   - Another team member's responsibility
   - Exposes standardized data through REST/WebSocket endpoints

F. Frontend / 3D Visualization
   - Another team member's responsibility

The critical data flow is:

MODEL DATA
    ↓
MODEL PROCESSING / STANDARDIZATION
    ↓
COMMON MODEL GRID
    ↓
/model API
    ↓
GRAPH FUSION
    ↓
DRIFT MEMORY
    ↓
ALERTS
    ↓
VISUALIZATION

My task is NOT to implement Graph Fusion, Drift Memory, the frontend, WebSockets, or the in-situ pipeline.

My task is to make the MODEL side of this pipeline reliable and integration-ready.

============================================================
2. MY EXACT RESPONSIBILITY
============================================================

Build the Ocean Model Data Pipeline with these responsibilities:

1. Acquire ocean model/reanalysis data.
2. Use INCOIS LAS as the PRIMARY source.
3. Use Copernicus Marine GLORYS as the FALLBACK source.
4. Process NetCDF/gridded scientific data using xarray + netCDF4.
5. Restrict the demo region to the BAY OF BENGAL.
6. Support the required model variables:
   - SST / Sea Surface Temperature
   - U current
   - V current
   - Wave Height
   - Salinity
   - Chlorophyll
7. Validate the incoming scientific data.
8. Normalize variable names, dimensions, coordinates, units, and timestamps where necessary.
9. Regrid model data to a clearly defined COMMON TARGET GRID.
10. Produce a stable, standardized internal representation.
11. Make the processed data consumable by the backend's /model interface.
12. Provide a deterministic local/demo fallback dataset so the complete system does not depend on an external data server during judging or rehearsal.
13. Provide tests and documentation for all critical processing stages.

The project architecture explicitly uses xarray/netCDF4 for gridded ocean-data processing and regrids the data to a common resolution before exposing it downstream. Do not replace this architecture with a different technology without first explaining why and getting approval. 

============================================================
3. IMPORTANT ARCHITECTURAL BOUNDARIES
============================================================

DO NOT implement these components unless a small compatibility stub is absolutely necessary:

- Graph Neural Network / Graph Fusion Engine
- Drift Memory Engine
- Alert scoring / alert generation logic
- Real-time streaming engine
- ConvLSTM Nowcast
- Argo / Glider ingestion
- NOAA WOD ingestion
- FastAPI endpoint implementation
- WebSocket implementation
- CesiumJS / Three.js frontend

Other team members own those areas.

Your output must be cleanly consumable by them.

============================================================
4. SCIENTIFIC DATA SOURCES
============================================================

PRIMARY:
INCOIS LAS

FALLBACK:
Copernicus Marine GLORYS reanalysis

Project framing:
The intended system is designed around INCOIS/INDOFOS operational model outputs, but the demo may run using an equivalent publicly accessible reanalysis source when direct operational access is unavailable.

Do NOT falsely claim that we have direct live operational access if the environment does not actually provide it.

The implementation must clearly distinguish:

SOURCE = INCOIS_LAS
SOURCE = COPERNICUS_GLORYS
SOURCE = LOCAL_DEMO

This source provenance must remain available in metadata.

============================================================
5. DEMO SCOPE
============================================================

Region:
BAY OF BENGAL

Do not download/process an unnecessarily large global dataset for the demo.

The system should support a configurable geographic bounding box so the region can be changed later, but the default configuration MUST be Bay of Bengal.

The target variable set is:

temperature / SST
u current
v current
wave height
salinity
chlorophyll

Do not silently drop a variable.

If a variable is unavailable in a particular source:

1. Detect it explicitly.
2. Record the problem.
3. Attempt the configured fallback source if appropriate.
4. Never silently substitute a scientifically different variable.
5. Never fabricate data.

============================================================
6. TARGET INTERNAL DATA MODEL
============================================================

Create one canonical internal representation for model data.

The rest of the application must not need to understand whether the source was INCOIS LAS or GLORYS.

The canonical model dataset should conceptually contain:

- time
- latitude
- longitude
- sst
- u_current
- v_current
- wave_height
- salinity
- chlorophyll

Scientific dimension information such as depth must be preserved where applicable rather than unnecessarily discarded.

The exact internal xarray Dataset structure should be well defined and documented.

Normalize source-specific variable names into the canonical names above.

Example:

source variable → canonical variable

temperature / thetao → sst
uo → u_current
vo → v_current
wave-related source field → wave_height
so → salinity
chl → chlorophyll

IMPORTANT:
Do NOT assume the examples above are universally correct for every dataset.
Inspect the actual dataset metadata first and create explicit source mappings.

============================================================
7. PROCESSING PIPELINE
============================================================

The pipeline must follow this logical sequence:

SOURCE SELECTION
    ↓
DATA INGESTION
    ↓
DATASET VALIDATION
    ↓
VARIABLE MAPPING
    ↓
REGION EXTRACTION
    ↓
UNIT / METADATA NORMALIZATION
    ↓
MISSING-DATA HANDLING
    ↓
COMMON TARGET GRID
    ↓
REGRIDDING
    ↓
QUALITY CHECK
    ↓
CANONICAL MODEL DATASET
    ↓
SERIALIZATION / API HANDOFF

Do not reorder these steps casually.

Each stage should be independently testable.

============================================================
8. CHECKPOINT-BASED IMPLEMENTATION
============================================================

You MUST work in checkpoints.

DO NOT build the whole system in one shot.

After completing a checkpoint:
1. Run the relevant tests.
2. Show me what was implemented.
3. Show files changed.
4. Show how to run/test it.
5. State any assumptions.
6. State any unresolved issues.
7. STOP and wait for approval before starting the next checkpoint.

Never silently continue to later checkpoints.

============================================================
CHECKPOINT 0 — REPOSITORY & ARCHITECTURE INSPECTION
============================================================

Before writing code:

1. Inspect the complete repository structure.
2. Identify:
   - Python version
   - package manager
   - existing source directories
   - existing configuration files
   - existing API contracts
   - existing data models/schemas
   - existing tests
   - environment/configuration handling
   - Docker configuration, if present
   - existing model-data code, if any
3. Identify whether another developer has already created:
   - /model schema
   - shared types
   - common configuration
   - API contract
4. DO NOT duplicate existing abstractions.
5. DO NOT overwrite unrelated team members' work.
6. DO NOT make broad architectural changes.

Deliver:
- repository assessment
- proposed files/modules for my component
- dependencies required
- integration assumptions
- exact implementation plan

Then STOP.

============================================================
CHECKPOINT 1 — DATA CONTRACT + CONFIGURATION
============================================================

Define the configuration required by the model pipeline.

At minimum:

- primary source
- fallback source
- demo/local source
- Bay of Bengal bounding box
- target spatial resolution
- time range
- required variables
- variable mappings
- units
- missing-value policy
- regridding method
- output format

Do NOT hard-code important configuration throughout Python files.

Use a central configuration mechanism appropriate to the existing project.

Create a documented canonical model-data schema.

Create validation for the schema.

Deliver:
- configuration
- canonical schema
- validation
- unit tests
- example configuration
- example dataset metadata

Then STOP.

============================================================
CHECKPOINT 2 — INCOIS LAS INGESTION
============================================================

Implement the primary INCOIS LAS ingestion layer.

Requirements:

1. Connect to the configured INCOIS LAS resource.
2. Load the required NetCDF/gridded data using xarray/netCDF4.
3. Inspect and validate dimensions.
4. Inspect coordinates.
5. Inspect available variables.
6. Inspect units.
7. Map source variables to canonical variable names.
8. Preserve metadata and provenance.
9. Fail clearly when required data is missing.
10. Do not silently continue with corrupted or incomplete scientific data.

Important:
The ingestion layer should return a standardized intermediate representation rather than passing raw source-specific objects throughout the application.

Add tests using local fixture data.

DO NOT require the test suite to contact a live external service.

Deliver:
- INCOIS ingestion module
- fixture/sample dataset if necessary
- source mapping
- validation
- unit tests
- usage example

Then STOP.

============================================================
CHECKPOINT 3 — GLORYS FALLBACK
============================================================

Implement Copernicus GLORYS as the fallback source.

Architecture:

              ┌── INCOIS LAS ────┐
REQUEST ──────┤                  ├──→ COMMON MODEL FORMAT
              └── GLORYS FALLBACK┘

Requirements:

1. The fallback mechanism must be explicit.
2. Do not hide source switching.
3. Record provenance.
4. Normalize GLORYS into the exact same canonical structure.
5. Keep source-specific parsing isolated.
6. The rest of the pipeline must not care which source was used.

Add tests proving:

INCOIS input → canonical format

GLORYS input → canonical format

Both produce compatible schemas.

Deliver:
- GLORYS ingestion module
- source-selection logic
- fallback behavior
- tests
- provenance metadata

Then STOP.

============================================================
CHECKPOINT 4 — REGION EXTRACTION
============================================================

Implement Bay of Bengal spatial extraction.

Requirements:

1. Use configurable geographic bounds.
2. Default = Bay of Bengal.
3. Preserve latitude/longitude correctly.
4. Handle coordinate ordering correctly:
   - ascending
   - descending
5. Correctly handle longitude conventions when necessary.
6. Validate that the extracted region actually contains data.
7. Do not assume the source uses the same coordinate names or orientation.

Add tests for:

- standard ascending coordinates
- descending latitude
- bounding-box extraction
- empty region
- boundary conditions

Deliver:
- region extraction module
- tests
- clear configuration

Then STOP.

============================================================
CHECKPOINT 5 — VARIABLE + UNIT NORMALIZATION
============================================================

Build a dedicated normalization layer.

For each required variable:

1. Detect source representation.
2. Map it to canonical representation.
3. Validate physical units.
4. Convert units only when conversion is scientifically valid and explicitly defined.
5. Record resulting units in metadata.
6. Reject ambiguous or unsupported units instead of guessing.

Required canonical variables:

sst
u_current
v_current
wave_height
salinity
chlorophyll

Do NOT fabricate a variable simply because the rest of the pipeline expects it.

Add data-quality checks for:
- NaN
- Inf
- impossible values
- missing variables
- duplicate coordinates
- malformed timestamps

Use scientifically defensible validation ranges/configuration and clearly document them.

Deliver:
- normalization module
- unit conversion module
- validation rules
- tests
- documentation

Then STOP.

============================================================
CHECKPOINT 6 — COMMON GRID + REGRIDDING
============================================================

Implement the common target grid.

This is a critical integration requirement.

Why:
The model grid and the real in-situ observations may not share identical spatial locations/resolution.

The processed model state therefore needs to be spatially standardized before entering downstream fusion.

Requirements:

1. Define the target latitude/longitude grid.
2. Make resolution configurable.
3. Select and document the interpolation/regridding method.
4. Preserve time.
5. Preserve variable metadata.
6. Handle NaNs appropriately.
7. Do not silently create physically misleading values.
8. Validate the resulting grid.
9. Ensure all required variables align to the same spatial coordinates.

The output must have a predictable grid that Person 1's Graph Fusion Engine can consume.

Add numerical sanity tests.

Deliver:
- target grid generator
- regridding module
- tests
- before/after example
- documentation explaining the chosen method

Then STOP.

============================================================
CHECKPOINT 7 — END-TO-END MODEL PIPELINE
============================================================

Combine the components into:

SOURCE
→ VALIDATE
→ MAP
→ EXTRACT BAY OF BENGAL
→ NORMALIZE
→ REGRID
→ QUALITY CHECK
→ CANONICAL DATASET

Create a single clean pipeline entry point.

Example conceptual interface:

load_model_data(...)
process_model_data(...)
prepare_model_dataset(...)

The exact function names are your choice, but the abstraction must remain clear.

The end-to-end pipeline must support:

PRIMARY:
INCOIS

FALLBACK:
GLORYS

LOCAL:
demo fixture

The local/demo path is important because the judging environment must not depend entirely on an external data source.

Deliver:
- end-to-end pipeline
- integration tests
- example execution
- generated canonical dataset

Then STOP.

============================================================
CHECKPOINT 8 — /MODEL INTEGRATION CONTRACT
============================================================

Do NOT implement FastAPI if another team member owns it.

Instead, prepare the model pipeline specifically for consumption by the backend.

Define and document what the /model endpoint needs to receive from your component.

The model layer should provide:

- timestamp
- geographic coordinates
- required model variables
- units
- grid metadata
- source/provenance
- processing metadata
- data quality metadata where useful

Coordinate with the existing API contract if it exists.

Do not invent a competing schema.

If an API contract already exists:
ADAPT THE PIPELINE TO IT.

If no contract exists:
propose one based on the project's architecture, clearly label it as a proposed interface, and STOP for approval before implementation.

Deliver:
- integration contract
- example JSON response/payload if required
- schema validation
- compatibility tests

Then STOP.

============================================================
CHECKPOINT 9 — GRAPH FUSION HANDOFF TEST
============================================================

This checkpoint exists only to verify compatibility with Person 1.

Do not implement Graph Fusion.

Instead:

1. Create a realistic model dataset.
2. Verify coordinates are aligned and predictable.
3. Verify all expected variables are available.
4. Verify timestamps are valid.
5. Verify the output can be consumed by the Graph Fusion input interface.
6. Test at least one complete data handoff using real processed model data.

The goal is:

REAL MODEL DATA
    +
REAL IN-SITU DATA
    ↓
GRAPH FUSION

Your component is responsible only for making the model side valid.

Deliver:
- integration test
- sample handoff
- compatibility report

Then STOP.

============================================================
CHECKPOINT 10 — DEMO HARDENING
============================================================

Prepare the component for national-level judging/demo conditions.

Add:

1. Deterministic demo dataset.
2. Local/offline execution mode.
3. External-source failure handling.
4. Clear logging.
5. Data provenance.
6. Validation reports.
7. Reproducible commands.
8. Error messages that are understandable to developers.
9. Tests for failure scenarios.
10. Minimal performance measurements.

The demo should remain functional even if the external source is temporarily unavailable.

Do not fake live data.

If the demo uses stored open reanalysis data, explicitly label it as such.

============================================================
9. CODE QUALITY REQUIREMENTS
============================================================

Follow these rules strictly:

- Python type hints wherever practical.
- Clear module boundaries.
- Small, testable functions.
- No giant monolithic script.
- No hidden global state.
- No hard-coded paths.
- No hard-coded secrets.
- No silently swallowed exceptions.
- No bare except blocks.
- Explicit logging for source selection/failure.
- Useful error messages.
- Unit tests for transformation logic.
- Integration tests for pipeline stages.
- Keep scientific metadata intact.
- Avoid unnecessary dependencies.
- Reuse existing project utilities before creating new ones.
- Do not modify unrelated modules.
- Do not rename shared interfaces without checking the rest of the repository.

============================================================
10. SCIENTIFIC CORRECTNESS REQUIREMENTS
============================================================

This project is an ocean-data digital twin.

Therefore:

- Never fabricate observations.
- Never invent model values.
- Never silently substitute one physical variable for another.
- Never assume units.
- Never assume coordinate names.
- Never assume latitude ordering.
- Never assume longitude convention.
- Never silently discard missing values.
- Never silently ignore missing variables.
- Never silently switch data sources.
- Preserve provenance.
- Make preprocessing decisions explicit and reproducible.

When unsure about the scientific meaning of a field, inspect its metadata and STOP rather than guessing.

============================================================
11. PERFORMANCE EXPECTATION
============================================================

Do not load unnecessarily large global datasets entirely into memory.

Use appropriate xarray techniques such as:

- slicing
- lazy loading where practical
- chunking where appropriate
- selecting only required variables
- selecting only the Bay of Bengal region
- limiting the time range for the demo

Do not prematurely optimize at the expense of correctness.

============================================================
12. TESTING STRATEGY
============================================================

Create tests for:

A. Source ingestion
B. Variable mapping
C. Region extraction
D. Coordinate normalization
E. Unit normalization
F. Missing-value handling
G. Regridding
H. Provenance
I. Source fallback
J. End-to-end processing
K. API compatibility
L. Failure scenarios

Use local fixtures/mocks for external data.

The test suite must not depend on uninterrupted network access.

============================================================
13. DOCUMENTATION
============================================================

Create documentation explaining:

1. What this component does.
2. Architecture.
3. Data sources.
4. Source fallback strategy.
5. Variables.
6. Canonical schema.
7. Units.
8. Coordinate conventions.
9. Bay of Bengal bounds.
10. Regridding strategy.
11. Missing-data policy.
12. Provenance.
13. Configuration.
14. How to run locally.
15. How to run tests.
16. How the backend consumes the output.
17. How Graph Fusion consumes the output.
18. Known limitations.

The documentation must distinguish between:

- actual implemented functionality
- demo functionality
- future scope

============================================================
14. FAILURE HANDLING
============================================================

Expected failures include:

- INCOIS unavailable
- GLORYS unavailable
- malformed NetCDF
- missing variable
- invalid units
- incompatible coordinates
- empty Bay of Bengal region
- unsupported dataset
- NaN-heavy field
- corrupt timestamp
- incompatible API schema

For each failure:

1. Detect it.
2. Explain it clearly.
3. Recover safely where a defined fallback exists.
4. Otherwise fail fast.

Never silently produce a scientifically invalid dataset.

============================================================
15. DEMO OUTPUT
============================================================

At the end of implementation I should be able to demonstrate:

1. Model data source selected.
2. Bay of Bengal extracted.
3. Required variables identified.
4. Data validated.
5. Data standardized.
6. Model data regridded.
7. Canonical model dataset produced.
8. Dataset passed to the backend/model interface.
9. The data can be consumed by Graph Fusion.

The core demo requirement is:

REAL MODEL DATA
    +
REAL IN-SITU DATA
    ↓
GRAPH FUSION
    ↓
DRIFT MEMORY
    ↓
ALERT

Your responsibility is the REAL MODEL DATA side of this pipeline.

============================================================
16. VERY IMPORTANT WORKING RULE
============================================================

Do not rush through all checkpoints.

Start with CHECKPOINT 0 only.

First inspect the existing repository and report:

- architecture you found
- existing relevant files
- existing contracts
- what you will create
- any conflicts
- any assumptions
- dependencies required

DO NOT write implementation code until CHECKPOINT 0 is reviewed.

After each checkpoint, STOP and wait for approval.

Do not invent requirements that are not present in this specification or the existing repository.

When there is ambiguity, ask instead of guessing.

============================================================
17. SUCCESS CRITERION
============================================================

The component is successful only when:

INCOIS LAS / GLORYS
        ↓
Validated Model Data
        ↓
Bay of Bengal
        ↓
Five-variable canonical dataset
        ↓
Common spatial grid
        ↓
Stable model output
        ↓
/model integration contract
        ↓
Graph Fusion compatible

and the complete component has automated tests, documentation, provenance, fallback behavior, and a deterministic demo path.

START NOW WITH CHECKPOINT 0 ONLY.