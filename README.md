# VARUNA — Visualization & Assimilation of Real-time Underwater Network Analytics

A browser-based 3D ocean digital twin that fuses numerical ocean model
output with in-situ sensor observations, and flags when the model and
reality disagree.

> "From coordinates to currents."

Smart India Hackathon 2026 — Problem Statement SIH26067

---

## Table of Contents

| Section | Description |
|---------|-------------|
| [What This Project Delivers](#what-this-project-delivers) | Capabilities and system output |
| [The Problem](#the-problem) | Why this project exists |
| [The Solution](#the-solution) | Graph-based fusion approach |
| [System Architecture](#system-architecture) | The six-service breakdown |
| &emsp;[Service 1 — Model Pipeline](#service-1--model-pipeline) | Gridded ocean model ingestion |
| &emsp;[Service 2 — In-Situ Pipeline](#service-2--in-situ-pipeline) | Sensor observation ingestion |
| &emsp;[Service 3 — Graph Fusion Engine](#service-3--graph-fusion-engine) | GNN correction layer |
| &emsp;[Service 4 — Drift Detection](#service-4--drift-detection) | Model-observation divergence alerts |
| &emsp;[Service 5 — REST Gateway](#service-5--rest-gateway) | Unified API surface |
| &emsp;[Service 6 — 3D Frontend](#service-6--3d-frontend) | React + Three.js digital twin |
| [Design Principles](#design-principles) | Contracts, adapters, fallbacks |
| [How the Pipeline Works](#how-the-pipeline-works) | End-to-end data flow |
| [Validation & Results](#validation--results) | Metrics and test coverage |
| [Data Sources](#data-sources) | What runs where |
| [Compared to Existing Tools](#compared-to-existing-tools) | Where VARUNA differs |
| [Impact](#impact) | Who this is for |
| [Feasibility](#feasibility) | Why this is buildable |
| [Running Locally](#running-locally) | Setup instructions |
| [Tech Stack](#tech-stack) | Technologies and tools used |
| [Roadmap](#roadmap) | Where this is heading |
| [Presentation](#presentation) | Full pitch deck |
| [Author](#author) | Project credits |

---

## What This Project Delivers

VARUNA is a six-service platform that takes a gridded ocean forecast and a
scatter of real sensor readings, reconciles them into one corrected field,
and renders the result as an explorable 3D globe.

- **Graph-Based Fusion** — A graph neural network corrects a 756-point
  ocean model grid against 29 sensor stations, learning spatial
  relationships rather than applying distance-weighted interpolation.
- **Continuous Drift Detection** — Model-observation divergence is scored
  automatically and surfaced as live alerts, replacing periodic manual
  validation.
- **Trust-Scored Visualization** — Every sensor marker carries a
  confidence score, so a researcher can see at a glance where the model
  and the ocean disagree.
- **Dual-Audience Interface** — A dense scientific view for researchers
  and a simplified safe/caution/avoid view for coastal communities.
- **Degrades Instead of Breaking** — Every upstream has a tested fallback.
  No single service failure takes the platform to zero.

---

## The Problem

Ocean forecasting agencies run numerical models and separately collect
sensor data from Argo floats, gliders, CTD casts, and moored buoys. The
comparison between the two happens manually, in desktop tools, on a
periodic schedule.

- Model output and in-situ observations live in separate tools with no
  unified view
- Validation requires researcher intervention for every data source
- Divergence between model and reality is caught late, if at all
- Existing viewers are 2D, depth-flat, and expert-only

> What if the comparison ran continuously, and told you the moment the
> model stopped matching the ocean?

---

## The Solution

<img width="3000" alt="System Architecture" src="https://github.com/user-attachments/assets/4dcf0781-7d28-4372-8c49-a8e96c3488a7" />

> Fuse → Detect → Validate → Serve → Show

VARUNA treats the model grid and the sensor network as one graph. Grid
points and sensor stations become nodes; spatial proximity becomes edges.
A GNN learns the correction from observed nodes and propagates it across
the field.

Where classical interpolation weights by distance alone, the graph
formulation lets the correction follow the structure of the data — and
because the model trains per request on the current snapshot, it adapts
as sensors come and go.

---

## System Architecture

<img width="3000" alt="The Solution" src="https://github.com/user-attachments/assets/5778a577-11cc-494b-b1a5-0b061d7e1b45" />

```
[ Model Pipeline ]  ─┐
                     ├─►  [ Graph Fusion Engine ]  ─►  [ Drift Detection ]
[ In-Situ Pipeline ]─┘              │                          │
                                    ▼                          ▼
                             [ REST Gateway ]  ─────►  [ 3D Frontend ]
```

---

## Service 1 — Model Pipeline

Ingests gridded ocean model output and normalizes it into the shared
schema.

| Aspect | Detail |
|--------|--------|
| Input | NetCDF, CF-convention aware |
| Variables | Sea surface temperature, currents, salinity, depth |
| Output | 756-point normalized grid snapshot |
| Extensibility | Adapter per source — new products plug in without touching downstream services |

---

## Service 2 — In-Situ Pipeline

Ingests point observations from the sensor network.

| Aspect | Detail |
|--------|--------|
| Sources | Argo floats, gliders, CTD casts, moored buoys |
| Stations | 29 in the demo region |
| Parsing | Per-record resilient — one malformed reading does not fail the batch |
| Output | Normalized observation records matching the fusion input contract |

---

## Service 3 — Graph Fusion Engine

**Framework:** PyTorch Geometric + FastAPI

The core of the system. Builds a graph over model grid points and sensor
stations, then trains a GCN to correct the model field toward the
observations.

- Trains per request on the current snapshot — no stale global model
- **Leave-sensors-out validation** on every run: a held-out subset of
  stations measures whether the correction actually generalizes
- **Content-hash caching** — identical input skips retraining entirely
- **Graph-weighted fallback** — when sensor count is too low to train,
  a non-GNN weighted correction runs instead

---

## Service 4 — Drift Detection

Scores divergence between the fused field and incoming observations, and
raises alerts when the model stops tracking reality.

| Output | Purpose |
|--------|---------|
| Divergence score | Per sub-region measure of model-observation disagreement |
| Alert feed | Ranked list of regions where drift exceeds threshold |
| Trust weight | Per-station confidence, consumed by the frontend overlay |

---

## Service 5 — REST Gateway

**Framework:** FastAPI

Single API surface over all upstream services.

| Endpoint | Purpose |
|----------|---------|
| `GET /model` | Normalized model grid snapshot |
| `GET /observations` | In-situ sensor records |
| `GET /fused` | Corrected field with per-point confidence |
| `GET /alerts` | Active drift alerts |

---

## Service 6 — 3D Frontend

**Framework:** React 19 + TypeScript + Three.js

An interactive digital twin rendered in the browser.

| Element | Description |
|---------|-------------|
| 3D globe | Explorable ocean surface with the fused field rendered as a colour field |
| Trust-scored markers | Sensor stations sized and coloured by confidence |
| Click-to-inspect | Modal showing a station's readings and local spatial context |
| Dual-mode toggle | Expert scientific view / simplified public view |
| Live alert feed | Consumes the drift service and surfaces active alerts |

---

## Design Principles

The interesting engineering problem here was never the model. It was
making six services survive each other.

- **One shared contract.** Every service reads and writes Pydantic
  schemas defined once and matched field-for-field across boundaries.
- **Swappable adapters.** Each upstream can be called in `mock`, `http`,
  or `in-process` mode. The same code path runs in tests, in local dev,
  and in deployment.
- **Fallback on every hop.** If an upstream is down, malformed, or slow,
  the caller degrades to a tested lightweight path rather than failing.
  The platform never breaks to zero.
- **54 automated tests** across the stack, covering the contracts, the
  fallbacks, and the fusion validation.

---

## How the Pipeline Works

1. Model pipeline pulls a gridded snapshot and normalizes it to the
   shared schema
2. In-situ pipeline pulls sensor records and normalizes them the same way
3. Fusion engine builds a graph over grid points and stations
4. GCN trains on observed nodes, with a held-out station subset reserved
   for validation
5. Corrected field is returned with per-point confidence, and cached
   against the input hash
6. Drift service compares the fused field to observations and scores
   divergence
7. Gateway exposes model, observations, fused field, and alerts over REST
8. Frontend renders the globe, the trust overlay, and the live alert feed

---

## Validation & Results

| Metric | Value |
|--------|-------|
| Model grid points | 756 |
| Sensor stations | 29 |
| Validation method | Leave-sensors-out on held-out stations |
| Automated tests | 54 |
| Fallback coverage | Every upstream call path |
| Cache behaviour | Content-hash — unchanged input skips retraining |

---

## Data Sources

The demo runs in local mode against a bundled demo dataset so the whole
pipeline is reproducible without credentials.

| Layer | Demo mode | Production path |
|-------|-----------|-----------------|
| Ocean model | Bundled demo grid | INCOIS LAS / Copernicus Marine (GLORYS), NetCDF |
| In-situ | Bundled demo observations | Argo, glider, CTD, and buoy feeds |

Both pipelines use the adapter pattern, so switching from demo to live
sources is a configuration change, not a rewrite.

---

## Compared to Existing Tools

<img width="3000" alt="Comparison with existing tools" src="https://github.com/user-attachments/assets/289fcfd8-7603-4874-92e1-c6200f2c7acb" />

**Current build status:** graph fusion, drift alerts, trust overlay, the
adapter layer, and the dual-mode 3D frontend are implemented and tested.
Depth-resolved isosurface rendering and the full interactive control set
(depth-slice, colorbar editor, vertical exaggeration) are on the roadmap
below, not yet shipped.

---

## Impact

<img width="3000" alt="Impact and benefits" src="https://github.com/user-attachments/assets/4e5bd2ba-6903-4396-ac8f-2612133bb118" />

---

## Feasibility

<img width="3000" alt="Feasibility and viability" src="https://github.com/user-attachments/assets/a0b29d72-45c8-4e33-95e6-e91250684152" />

---

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Start the fusion engine
uvicorn fusion.main:app --port 8001

# Start the drift service
uvicorn drift.main:app --port 8002

# Start the gateway
uvicorn gateway.main:app --port 8000

# Start the frontend
cd frontend && npm install && npm run dev
```

Run the test suite:

```bash
pytest
```

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Graph learning | PyTorch Geometric |
| Backend services | FastAPI + Pydantic |
| Data handling | xarray, NumPy, Pandas |
| Frontend | React 19 + TypeScript + Vite |
| 3D rendering | Three.js |
| Styling | Tailwind CSS |
| Testing | pytest |

---

## Roadmap

- Swap demo adapters for live INCOIS and Copernicus feeds
- WebSocket push in place of polling for the alert feed
- OGC WMS/WCS and OPeNDAP endpoints so other tools can consume the
  fused field directly
- Isosurface extraction for depth-resolved volume rendering
- Full interactive control set — depth-slice, colorbar editor, vertical
  exaggeration
- Extend beyond the demo region — the graph formulation is not
  basin-specific

---

## Presentation

Full pitch deck — Smart India Hackathon 2026, Problem Statement SIH26067:

[View Full Presentation (PDF)](https://github.com/user-attachments/files/32061595/SIH-67_.pdf)

---

## Author

**Ragini Pawar** — Developer

GitHub: [github.com/Raginipawar/Ocean_situ](https://github.com/Raginipawar/Ocean_situ)

---

> "The comparison should not wait for someone to run it."
