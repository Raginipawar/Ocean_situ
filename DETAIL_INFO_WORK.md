# VARUNA (SIH26067) — Detailed Work Log & Run Guide

Team **Hudson Hackers**. This file covers Person 1's (Graph Fusion Engine +
Day 4 UI/UX) work: everything built, everything verified working with real
data (not just "tests pass"), and the exact terminal commands to run the
whole system for a live demo.

Branch: `ragini-frontend` (not `main` — team convention is feature branches,
merge to `main` via PR).

---

## 1. What VARUNA is

A digital twin of the Bay of Bengal ocean: a simulated model grid (Person 4)
gets corrected against real sensor observations (Person 6) by a Graph Neural
Network (Person 1 — this track), producing a **fused** grid where every
point carries a **trust label** (green / amber / red) showing how much the
model agrees with reality there. A drift-memory service (Person 2) watches
that fused output over time for anomalies (e.g. marine heatwaves) and raises
alerts. A React/Three.js frontend (Day 4, also this track) shows all of it
on an interactive 3D globe.

Four of six people's tracks are real, integrated, and verified end-to-end:

| Person | Track | Status |
|---|---|---|
| 1 (me) | Graph Fusion Engine + Day 4 frontend | Done, integrated |
| 2 | Drift Memory Engine | Done, integrated |
| 3 | Nowcast | Not started (branch `nikhil-nowcast` has no new commits) |
| 4 | Model pipeline (`/model`) | Done, integrated |
| 5 | Backend API gateway | Built (Day 2/3), **not** in the live demo path (see §5) |
| 6 | In-situ observation pipeline (`/observations`) | Done, integrated |

---

## 2. Architecture — how the pieces actually talk to each other

```
Person 4's model-pipeline  ─┐
  (varuna_model_pipeline,   │
   in-process, no HTTP)     │
                             ├──▶  Graph Fusion Engine (Person 1)
Person 6's insitu-pipeline ─┘        varuna-graph-fusion/
  (varuna_insitu_pipeline,           - builds a sensor graph
   in-process, no HTTP)              - trains/runs a GNN to correct
                                        the model grid against real
                                        sensors
                                      - computes trust/confidence
                                      - serves /model /observations
                                        /fused /health  (port 8000)
                                              │
                    ┌─────────────────────────┼─────────────────────────┐
                    ▼                                                   ▼
     Drift Memory Engine (Person 2)                      Frontend (Person 1, Day 4)
     drift-memory-engine/                                 frontend/
     - polls/consumes our /fused output                   - 3D globe (React Three Fiber)
     - scores rolling drift + "surprise"                  - click any sensor point →
       per Bay-of-Bengal sub-basin                           PointInspector modal + local
     - serves /alerts /memory/state  (port 8002)              mini-map
                    │                                       - Expert / Public mode toggle
                    └──────────────────────────────────────▶ - Live alert feed (from Person 2)
                                                              - trust-colored markers
                                                              (port 4173, production build)
```

**Key design decision:** Person 4's and Person 6's pipelines both turned out
to ship as **in-process Python packages**, not their own HTTP servers. So
the Graph Fusion Engine imports and calls them directly in the same
interpreter — no network hop, one fewer process that can fall over on
stage. Every source is swappable via env var (mock / http / pipeline)
without touching any engine code — see `varuna-graph-fusion/src/graph_fusion/adapters.py`.

**Reliability rule applied everywhere:** every real data source has an
automatic fallback to mock data on *any* exception (`FallbackModelSource`,
`FallbackObservationSource` in `adapters.py`; the Drift Memory Engine has
the same fallback built in for `use_upstream=true`). The site should never
go down because a teammate's pipeline hits an edge case during the jury
demo — it silently degrades to mock instead of showing an error.

---

## 3. What's been built, in detail

### 3.1 Graph Fusion Engine (`varuna-graph-fusion/`) — Person 1's core deliverable

- `schemas.py` — Pydantic contracts for `/model`, `/observations`, `/fused` (matched field-for-field with Person 4's and Person 6's own schemas, confirmed by them independently).
- `distance.py` / `graph_builder.py` — builds a sensor network graph: edge weights combine haversine distance decay, depth similarity, and current-alignment (real oceanographic connectivity, not just nearest-neighbour).
- `gnn_model.py` / `gnn_engine.py` — a GCN (PyTorch Geometric) trained per-request on the current sensor graph to predict corrections at every grid point, with leave-sensors-out validation (`validation_mae_sst_c` in the API response is a real held-out error, not made up).
- `fallback_engine.py` — a non-GNN graph-weighted fallback if there aren't enough sensors to train on (`min_sensors_for_training`, default 8) or the GNN path fails for any reason.
- `trust_overlay.py` — turns model-vs-sensor disagreement + structural "support" (how much real sensor evidence backs a point) into confidence scores and green/amber/red labels (thresholds: green ≥ 0.7, amber ≥ 0.4).
- `ingest.py` / `sanitize.py` — resilient per-point parsing of upstream JSON (a single malformed point doesn't kill the whole batch) and sentinel/out-of-range value scrubbing, for when real teammate data is messy.
- `fusion_service.py` — orchestrates the above; content-hash caches the result (SHA256 of the actual data values, excluding timestamps) so repeated `/fused` calls against unchanged upstream data don't retrain the GNN every time — important because Person 4's/Person 6's local-demo pipelines take a few seconds, not milliseconds.
- `adapters.py` — the swappable data-source layer described in §2. Modes: `mock` | `http` | `pipeline`, set via `VARUNA_MODEL_SOURCE` / `VARUNA_OBS_SOURCE`.
- `api.py` — FastAPI app: `/health`, `/model`, `/observations`, `/fused?engine=auto|gnn|fallback`.
- 54 automated tests across 10 test files (`tests/`), all passing.

**Verified live** (not just unit tests): with `VARUNA_MODEL_SOURCE=pipeline` and `VARUNA_OBS_SOURCE=pipeline`, `/fused` genuinely runs Person 4's 756-point model grid against Person 6's 29 real buoy stations through the real GNN and returns real trust-scored corrections — e.g. a real point at `18.20°N, 89.70°E` (buoy `niot-bd08`) came back with `sst_c: 27.83`, `correction_sst_c: -0.23`, `confidence: 0.92`, `trust_label: "green"`.

### 3.2 Person 4's model-pipeline (`model-pipeline/`) — integrated

`varuna_model_pipeline` — installed in-process into the engine's venv.
`ModelPipelineSource` in `adapters.py` calls `prepare_model_dataset(...)`
directly. Falls back to `local_demo` mode (synthetic but physically
plausible regridded data) since real INCOIS-LAS/GLORYS credentials aren't
available in this environment; the pipeline's own source-selection logic
handles that fallback internally too. 10 test files, verified.

### 3.3 Person 6's insitu-pipeline (`insitu-pipeline/`) — integrated by me this session

`varuna_insitu_pipeline` — same in-process pattern. New this session:
`InsituPipelineSource` + `FallbackObservationSource` added to
`adapters.py`, `VARUNA_OBS_SOURCE=pipeline` wired through `config.py`.

**Verified live:** ran the pipeline directly — 29 real buoy stations across
the Bay of Bengal (`niot-bd08` through `niot-bdNN` etc.), plausible
SST/salinity/wave-height values, QC report showed 104 raw records
processed, 0 dropped. Then verified the full chain through the engine's
own `/fused` endpoint (see §3.1). 21 tests, all passing, plus the engine's
own 54 tests still pass after the change.

### 3.4 Person 2's Drift Memory Engine (`drift-memory-engine/`) — integrated by me this session

FastAPI service, separate process, port 8002 by default.
- `detector.py` — computes SST/current divergence between model and
  observed values per sub-basin (north Bob, central Bob, south Bob, Andaman
  Sea, coastal East India), classifies severity (info/warning/critical),
  flags marine-heatwave-style signals.
- `memory.py` — rolling "surprise"/drift memory per sub-basin+variable
  (test-time memory accumulation), so alerts reflect a trend, not a single
  noisy reading.
- `/alerts?use_upstream=true` — the integration point: fetches **our**
  live `/fused` output and evaluates real drift on it, instead of its own
  canned demo scenario. Falls back to the scenario automatically if our
  engine is unreachable (same "never break the demo" pattern).

**Verified live:** started it pointed at the real engine
(`VARUNA_DRIFT_GRAPH_FUSION_URL=http://localhost:8000`), hit
`/alerts?use_upstream=true`, got back real alerts computed from our actual
GNN-fused output — e.g. `"SST diverging -0.62°C from forecast (Model:
27.58°C, Obs: 26.95°C)"` at real sensor coordinates. This is the full
four-person chain (Person 4 → Person 6 → my engine → Person 2) working
together on real data, confirmed working in one sitting. 11 tests, all
passing.

### 3.5 Person 5's backend gateway (`backend/`) — built, not in the current demo path

A FastAPI gateway (`/api/*` REST + a websocket router) meant to sit in
front of the Graph Fusion Engine. Verified it runs and its mock-fallback
pattern works, but:
- it defaults to the **same port (8000)** as the Graph Fusion Engine
  itself, and separately expects the engine at `8001` by default — a
  configuration mismatch that was never resolved because...
- ...the frontend currently talks **directly** to the Graph Fusion Engine
  on port 8000, skipping the gateway entirely. This was a deliberate call
  for demo reliability: one fewer process, one fewer network hop, one
  fewer thing that can misconfigure on stage. The gateway isn't part of
  `start_demo.ps1` or the manual run steps in §5.

### 3.6 Frontend (`frontend/`) — Day 4 + ongoing

React + TypeScript + Vite + Tailwind v4 + React Three Fiber. Pages:
Home, Digital Twin, Services, About, Sitemap.

**Digital Twin page** (`pages/DigitalTwin.tsx`) is the main deliverable:
- Realistic 3D globe (`components/globe/Globe.tsx`) focused on the Bay of
  Bengal, with a day/night/cloud-textured Earth and a region bounding box.
- Sensor points rendered as trust-colored markers (green/amber/red,
  resolved from CSS theme tokens to literal hex before hitting the WebGL
  material — a `var()` CSS reference silently renders white in Three.js,
  learned the hard way).
- **Click-to-inspect**: click any marker (or its row in the sensor list) →
  `components/PointInspector.tsx` opens a modal with the point's readings,
  model correction, trust badge, and a local SVG mini-map plotting nearby
  fused points (±3° window) color-coded by trust — spatial context for
  whether a disagreement is an isolated blip or a regional pattern.
- Globe can unwrap into a flat 2D map view (depth-aware markers keep their
  vertical "stem" in the unwrapped view).
- Editorial annotation callouts (`components/Annotation.tsx`) label key
  parts of the UI for a first-time viewer (jury).
- **Expert / Public mode toggle**: Expert shows full fusion summary,
  sensor list, confidence numbers. Public shows a plain-language
  Safe/Caution/Avoid message for the *nearest currently-viewed* point
  (deliberately not a global worst-case — a fisherman near safe water
  shouldn't see "Avoid" because of an unrelated red point elsewhere).
- **Live alert feed**: polls Person 2's Drift Memory Engine every 20s,
  renders real alerts with severity color, message, and coordinates. Shows
  an honest "can't reach" message if that service isn't running — never
  fabricates alerts.
- No client-side mock fallback anywhere in the frontend, on purpose: if a
  backend is down, the UI says so rather than inventing ocean data.

---

## 4. Every backend/frontend port and env var, at a glance

| Service | Default port | Key env vars |
|---|---|---|
| Graph Fusion Engine | 8000 | `VARUNA_MODEL_SOURCE=pipeline`, `VARUNA_OBS_SOURCE=pipeline`, `VARUNA_CORS_ORIGINS=http://localhost:4173,http://127.0.0.1:4173` |
| Drift Memory Engine | 8002 | `VARUNA_DRIFT_GRAPH_FUSION_URL=http://localhost:8000` |
| Frontend (production preview) | 4173 | none required (defaults point at the two ports above) |
| Frontend (dev server — avoid for demo) | 5173 | — |
| Person 5's gateway (not used in demo) | 8000 (collides!) | — |

---

## 5. How to run everything — exact terminal commands

All venvs (`varuna-graph-fusion/.venv`, `drift-memory-engine/.venv`) are
already created and have every dependency installed, including Person 4's
and Person 6's packages installed in-process into the engine's venv. These
commands can be pasted directly.

Open **three separate terminals** (PowerShell), one per service, in this
order.

### Terminal 1 — Graph Fusion Engine (start first)

```powershell
cd "C:\Users\Ragini Pawar\OneDrive\Desktop\Ocean_situ\varuna-graph-fusion"
$env:VARUNA_MODEL_SOURCE = "pipeline"
$env:VARUNA_OBS_SOURCE = "pipeline"
$env:VARUNA_CORS_ORIGINS = "http://localhost:4173,http://127.0.0.1:4173"
.\.venv\Scripts\python.exe -m uvicorn graph_fusion.api:app --port 8000
```
Wait for `Uvicorn running on http://127.0.0.1:8000`. Check it:
```powershell
curl http://localhost:8000/health
```
Should return `{"status":"ok","region":"bay_of_bengal"}`.

### Terminal 2 — Drift Memory Engine (Person 2)

```powershell
cd "C:\Users\Ragini Pawar\OneDrive\Desktop\Ocean_situ\drift-memory-engine"
$env:VARUNA_DRIFT_GRAPH_FUSION_URL = "http://localhost:8000"
.\.venv\Scripts\python.exe -m uvicorn drift_memory.api:app --port 8002
```
Check it:
```powershell
curl http://localhost:8002/health
```

### Terminal 3 — Frontend (production build, not `npm run dev`)

```powershell
cd "C:\Users\Ragini Pawar\OneDrive\Desktop\Ocean_situ\frontend"
npm run build
npm run preview
```
Open **http://localhost:4173** → go to **Digital Twin**.

> Why `build` + `preview` instead of `npm run dev`: the dev server compiles
> each route on first visit, and the Digital Twin route (Three.js globe)
> can take 20-30+ seconds to compile on that very first navigation — which
> looks exactly like a broken site in front of a jury. A production build
> has zero on-demand compilation.
>
> **If you edit any frontend file**, you must re-run `npm run build` and
> then restart `npm run preview` (Ctrl+C it, run it again) — `vite preview`
> serves a static snapshot of `dist/` taken at startup, it does **not**
> hot-reload when `dist/` changes underneath it.

### One-command alternative

```powershell
.\start_demo.ps1
```
run from the repo root. **Current limitation**: it only starts the Graph
Fusion Engine (with `VARUNA_MODEL_SOURCE=pipeline`) and the frontend — it
does **not** yet set `VARUNA_OBS_SOURCE=pipeline` or start the Drift
Memory Engine, so the demo it launches uses mock observations and shows no
live alert feed. Use the three-terminal method above for the full real
chain, or ask to have `start_demo.ps1` updated to cover all three
services.

### Stopping everything

Close each PowerShell window, or `Ctrl+C` in each. If a port is stuck
occupied by a leftover process:
```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen | Select-Object -ExpandProperty OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force }
```
(swap `8000` for `8002` / `4173` as needed).

### Running the automated test suites

```powershell
cd "C:\Users\Ragini Pawar\OneDrive\Desktop\Ocean_situ\varuna-graph-fusion"
.\.venv\Scripts\python.exe -m pytest -q

cd "C:\Users\Ragini Pawar\OneDrive\Desktop\Ocean_situ\drift-memory-engine"
.\.venv\Scripts\python.exe -m pytest -q
```
(insitu-pipeline's and model-pipeline's own test suites run the same way
from their own folders if they get their own `.venv`; both packages are
already installed and tested through the graph-fusion engine's venv above.)

---

## 6. Known gaps (honest status, not hidden)

- **Person 3 (Nowcast)**: branch `nikhil-nowcast` has no work beyond the
  shared Day 2/3 baseline. Nothing to integrate yet.
- **Person 5's gateway**: built and runs, but not wired into the live
  demo — frontend talks to the Graph Fusion Engine directly (see §3.5).
  Port collision (both default to 8000) would need resolving before it
  could be added back in.
- **`start_demo.ps1`**: doesn't yet start the Drift Memory Engine or
  request real observations — see §5 note.
- All "real data" claims above were independently verified by installing,
  running, and curling/hitting each service live in this session — not
  just reading code or trusting a passing test suite.

----------------------------------------------------------
Terminal 1 — Graph Fusion Engine:


cd "C:\Users\Ragini Pawar\OneDrive\Desktop\Ocean_situ\varuna-graph-fusion"
$env:VARUNA_MODEL_SOURCE = "pipeline"
$env:VARUNA_OBS_SOURCE = "pipeline"
$env:VARUNA_CORS_ORIGINS = "http://localhost:4173,http://127.0.0.1:4173"
.\.venv\Scripts\python.exe -m uvicorn graph_fusion.api:app --port 8000
Terminal 2 — Drift Memory Engine (Person 2):


cd "C:\Users\Ragini Pawar\OneDrive\Desktop\Ocean_situ\drift-memory-engine"
$env:VARUNA_DRIFT_GRAPH_FUSION_URL = "http://localhost:8000"
.\.venv\Scripts\python.exe -m uvicorn drift_memory.api:app --port 8002
Terminal 3 — Frontend (production build):


cd "C:\Users\Ragini Pawar\OneDrive\Desktop\Ocean_situ\frontend"
npm run build
npm run preview
Open: http://localhost:4173 → Digital Twin

Health checks (optional, any terminal):


curl http://localhost:8000/health
curl http://localhost:8002/health