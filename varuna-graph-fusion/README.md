# VARUNA — Graph Fusion Engine

**SIH26067 · Team Hudson Hackers · Person 1 / Intelligence Core #1**

This is the engine that corrects the ocean forecast model grid using a graph
of real in-situ sensor readings — the primary technical differentiator the
whole VARUNA pitch rests on ("graph-based fusion, not distance-based
interpolation"). This README covers only this track. See
[`../Problem_approach/`](../Problem_approach) for the full team approach
document and work distribution, and the top-level
[`../README.md`](../README.md) for how this fits into the rest of VARUNA.

Status as of this build (Sept 6, Day 2 evening): **Day 1–2 of the 4-day
sprint plan (Sept 5–8) are done** — the graph structure is designed, the GNN
and fallback correction engines both run end-to-end against mock data, and
`/fused` is live. Person 4 and Person 6 haven't started their real
pipelines yet, so today's extra time went into de-risking Day 3 ahead of
time: resilient per-point parsing, physical-plausibility sanitization, and
response caching — see [Hardening for Day 3](#hardening-for-day-3) below,
and [`DAY3_INTEGRATION.md`](DAY3_INTEGRATION.md) for the handoff checklist
to send Person 4/6 once they're ready to wire in.

---

## 1. What this engine actually does

There are two disagreeing versions of the ocean:

- **`/model`** — the forecast (INCOIS/HYCOM-class reanalysis), a dense grid,
  owned by Person 4.
- **`/observations`** — real Argo/Glider/CTD/Buoy readings, sparse points,
  owned by Person 6.

This engine builds a **graph** where every sensor and every model grid cell
is a node, computes how strongly connected each pair of nodes really is in
the ocean (not just how close they are on a map), and uses that graph to
predict a correction at every grid point — including ones nowhere near a
sensor in a straight line, but well connected to one via a current.

The output is `/fused`: the corrected grid, plus a per-point **trust
overlay** (green/amber/red) the 3D visualization team draws directly on the
globe.

## 2. Why the graph is not just "nearest sensor wins"

Two points close in raw lat/lon can be poorly connected in the real ocean
(across a strong current front, or at very different depths). Two points
further apart but sitting along the same current can be strongly connected.
So every edge weight in this graph is:

```
weight = spatial_decay(distance) × depth_decay(|depth_a - depth_b|) × flow_multiplier(current_alignment)
```

- **`spatial_decay`** — closer points get more weight (exponential decay).
- **`depth_decay`** — points at similar depth get more weight (ocean
  stratification limits vertical mixing).
- **`flow_multiplier`** — points that lie along the local current direction
  get boosted weight; points across-current are damped, *even at the same
  distance*. This is the piece that makes it "oceanographic connectivity,"
  not distance.

See [`src/graph_fusion/distance.py`](src/graph_fusion/distance.py) for the
exact math, and its module docstring for the honest answer to "isn't this
just IDW with extra steps?".

A KD-tree is used to find *candidate* neighbours efficiently as the sensor
network scales (so the graph stays sparse, not fully connected — an O(n log n)
computational concern). It is **not** what decides edge strength; the
connectivity weight above is. See
[`src/graph_fusion/graph_builder.py`](src/graph_fusion/graph_builder.py).

## 3. Two engines, one automatic fallback

| Engine | File | Needs training? | When it runs |
|---|---|---|---|
| **GNN** (primary) | [`gnn_model.py`](src/graph_fusion/gnn_model.py), [`gnn_engine.py`](src/graph_fusion/gnn_engine.py) | Yes (seconds, CPU) | `engine=auto` or `engine=gnn`, when ≥8 sensors are available |
| **Graph-weighted fallback** | [`fallback_engine.py`](src/graph_fusion/fallback_engine.py) | No | Automatically, if the GNN fails or is skipped; always if `engine=fallback` |

The GNN is a small multi-layer GCN (Kipf & Welling) doing **semi-supervised
node regression**: sensor nodes are labelled with a known target (their
model-vs-observation residual), grid nodes are unlabelled, and the network
learns to propagate the residual across the connectivity-weighted graph.

**How we validate it without ground truth on the grid:** a random subset of
sensors is held out of the training loss entirely (their features are still
visible to the graph — exactly like a grid node — only their label is
hidden). The reported `validation_mae_sst_c` is the model recovering those
hidden sensors' true bias from graph context alone. That is the closest
honest proxy available for "would this be trustworthy at an actual
unobserved grid point," and it is the same transductive evaluation regime
used in the original semi-supervised GCN literature.

The **fallback engine** needs no training and cannot fail: for any node, it
walks the graph outward (1-hop, then 2-hop if still unreached) and takes an
edge-weight-weighted average of known sensor residuals — a graph diffusion /
weighted Nadaraya-Watson regression over the connectivity graph. This is the
engine named explicitly in the team's risk/fallback plan: *"fall back to the
simpler graph-weighted correction — it's still legitimately 'graph-based
fusion' under questioning."*

`FusionService` ([`fusion_service.py`](src/graph_fusion/fusion_service.py))
tries the GNN first under `engine=auto` and drops to the fallback
automatically on **any** exception (too few sensors, unstable/NaN loss,
degenerate graph) — this is what makes "never cut the core loop" a property
of the code, not a manual judgment call during the demo.

## 4. Trust overlay

Per point, two independent numbers are computed
([`trust_overlay.py`](src/graph_fusion/trust_overlay.py)):

- **`confidence`** (drives the green/amber/red `trust_label`) — how small the
  correction was, i.e. how well the model already matched reality there.
- **`support`** — how much real sensor evidence is actually behind this
  point, structurally, from the graph (sensors = 1.0; a grid point with no
  sensor within 2 hops → close to 0).

`support` **caps** `confidence`: a point with zero supporting evidence can
never show as confidently green just because its (uninformative) correction
happened to be small. This stops the overlay from being misleading in
data-sparse regions of the Bay of Bengal — a correctness property judges can
poke at directly.

## 5. API contract

Four endpoints per the team's architecture (`/alerts` belongs to Person 2's
Drift Memory Engine and isn't implemented here):

| Endpoint | Owner | This repo |
|---|---|---|
| `GET /model` | Person 4 (real pipeline) | Mock adapter, swappable |
| `GET /observations` | Person 6 (real pipeline) | Mock adapter, swappable |
| `GET /fused?engine=auto\|gnn\|fallback` | **Person 1 (this track)** | Fully implemented |
| `GET /health` | — | Implemented |

Full request/response shapes are in
[`src/graph_fusion/schemas.py`](src/graph_fusion/schemas.py) (Pydantic
models — also what FastAPI uses to generate the interactive docs at
`/docs`). This is a **proposed** contract so this track wasn't blocked
waiting on a group sync; confirm it with Person 4/5/6 and adjust only this
one file if it needs to change — nothing else in the package talks to raw
JSON.

## 5.5. Hardening for Day 3

Built ahead of time, while Person 4/6's real pipelines don't exist yet, so
wiring them in later is a config change rather than a debugging session
(full handoff doc: [`DAY3_INTEGRATION.md`](DAY3_INTEGRATION.md)):

- **[`ingest.py`](src/graph_fusion/ingest.py)** — resilient, per-point
  parsing for `HTTPModelSource`/`HTTPObservationSource`. Pydantic validates
  a `list[...]` all-or-nothing by default: one malformed reading from one
  flaky real sensor used to fail the *entire* snapshot. Now a bad point is
  dropped and logged; everything else still comes through.
- **[`sanitize.py`](src/graph_fusion/sanitize.py)** — filters QC/sentinel
  fill values (`-999`, `-9999`, etc.) and physically-impossible readings out
  before they reach the graph, so a miscalibrated or bad-fix sensor reads as
  "no data" rather than as a real value that would poison the correction.
  Verified: a sensor sending `-999` for SST does not produce a ~1000°C bogus
  correction — either no correction is applied, or (if a real neighbouring
  sensor exists) the graph propagates a sensible estimate to it instead.
- **Content-keyed caching** in `FusionService` — identical (model,
  observations, variables, engine) input returns the cached result instead
  of retraining the GNN from scratch (~2-3s). Keyed on actual values, not
  timestamps, so it never serves stale results once real streaming data is
  involved; a genuinely new reading changes the hash and triggers real
  recomputation. Measured: repeated identical calls go from ~3.8s to ~0.003s.

## 6. Project layout

```
varuna-graph-fusion/
├── src/graph_fusion/
│   ├── config.py           region/variable scope, all tunable knobs
│   ├── schemas.py          Pydantic contracts for /model, /observations, /fused
│   ├── distance.py         oceanographic connectivity weight (the core idea)
│   ├── graph_builder.py    builds the sensor+grid graph (KD-tree candidates + connectivity weights)
│   ├── mock_data.py        synthetic /model + /observations (incl. a synthetic marine heatwave)
│   ├── gnn_model.py        the GCN architecture
│   ├── gnn_engine.py       GNN training/inference + leave-sensors-out validation
│   ├── fallback_engine.py  training-free graph-weighted correction
│   ├── trust_overlay.py    confidence / support / green-amber-red scoring
│   ├── fusion_service.py   orchestrates sanitize → graph → engine (w/ auto-fallback + caching) → trust overlay
│   ├── ingest.py           resilient per-point parsing (Day 3 hardening)
│   ├── sanitize.py         QC/sentinel + physical-range filtering (Day 3 hardening)
│   ├── adapters.py         swap mock ↔ real /model & /observations sources
│   └── api.py              FastAPI app: /model /observations /fused /health
├── scripts/
│   ├── setup_env.ps1 / .sh  one-shot environment setup
│   ├── run_demo.py          CLI end-to-end demo, no server needed
│   └── visualize_graph.py   renders the sensor graph + trust overlay to a PNG
├── tests/                   50 tests covering every module above
├── data/sample/             generated demo artifacts (gitignored PNGs)
├── DAY3_INTEGRATION.md      handoff checklist for Person 4/6
├── requirements.txt
├── pyproject.toml
└── README.md                this file
```

## 7. Setup

Tested on **Windows 11, Python 3.14, CPU-only** (no GPU/CUDA required —
PyTorch and PyTorch Geometric both install and run fine CPU-only). Should
work unchanged on macOS/Linux.

```powershell
# from varuna-graph-fusion/
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu
pip install -e .
```

or just run the setup script:

```powershell
.\scripts\setup_env.ps1        # Windows
./scripts/setup_env.sh         # macOS / Linux
```

## 8. Running it

**Run the tests** (50 tests, ~10 seconds):

```powershell
python -m pytest -q
```

**Run the CLI demo** (no server, prints a full before/after report):

```powershell
python scripts/run_demo.py
python scripts/run_demo.py --n-sensors 60 --engine fallback
```

**Generate a graph + trust-overlay visualization** (saved to
`data/sample/sensor_graph.png`):

```powershell
python scripts/visualize_graph.py
```

**Run the API server:**

```powershell
uvicorn graph_fusion.api:app --reload --port 8000
```

Then, in another terminal (or via the interactive docs at
`http://localhost:8000/docs`):

```powershell
curl http://localhost:8000/health
curl http://localhost:8000/model
curl http://localhost:8000/observations
curl http://localhost:8000/fused
curl "http://localhost:8000/fused?engine=fallback"
```

## 9. Wiring in real data (Day 3)

Full handoff checklist for Person 4/6: [`DAY3_INTEGRATION.md`](DAY3_INTEGRATION.md).

When Person 4's `/model` and Person 6's `/observations` are live, point this
engine at them with environment variables — no code changes required outside
`adapters.py`:

```powershell
$env:VARUNA_MODEL_SOURCE = "http"
$env:VARUNA_MODEL_SOURCE_URL = "http://<person4-host>:8000/model"
$env:VARUNA_OBS_SOURCE = "http"
$env:VARUNA_OBS_SOURCE_URL = "http://<person6-host>:8000/observations"
uvicorn graph_fusion.api:app --port 8000
```

If the real payload shape differs slightly from
[`schemas.py`](src/graph_fusion/schemas.py), update the field names there —
`graph_builder.py`, both engines, and the trust overlay only ever read
through those typed models, never raw JSON.

## 10. Known limitations / honest scope

- Mock `/model` and `/observations` are synthetic but designed with a real
  gap baked in: the model background is a smooth field, while "truth"
  (sampled by `/observations`) also includes a localized marine-heatwave
  bump the model doesn't know about — so there's a genuine, non-trivial
  signal for the fusion engine to recover, not a toy that trivially matches.
- The candidate-edge search (KD-tree) is a computational optimisation, not
  the source of "connectivity" — see §2. This is worth stating proactively
  if asked "you still used nearest-neighbour search though?"
- ~~GNN training re-runs on every `/fused` call~~ — fixed: `FusionService`
  now caches by content hash of the actual (model, observations, variables,
  engine) values, so identical repeated calls return in ~3ms instead of
  retraining (~2-3s for a ~400-node graph on CPU). A genuinely new reading
  still triggers real recomputation — see §5.5.
- Full multi-variable support (SST, currents, wave height) is implemented,
  but per the team's fallback order, dropping to SST-only is a one-line
  config change (`config.VARIABLES = config.SST_ONLY_VARIABLES`) if
  currents/waves prove unstable under real data.
