# VARUNA — SIH26067

**Visualization & Assimilation of Real-time Underwater Network Analytics**
Smart India Hackathon 2026 · Team **Hudson Hackers** · Problem Statement
SIH26067 (Ministry of Earth Sciences, Disaster Management)

A browser-based living digital twin of the Indian Ocean that fuses
INCOIS/HOOFS-class forecast model output with real Argo/Glider/CTD/Buoy
observations, and actively flags when the model and reality disagree —
instead of leaving that comparison to manual, periodic desktop work.

Full pitch, architecture, feasibility, and research references:
[`Problem_approach/`](Problem_approach) (source PDFs — the team's approach
document and slide decks).

## What's in this repo

| Folder | What it is |
|---|---|
| [`Problem_approach/`](Problem_approach) | The team's approach document, SIH slide deck, and Round-2 work-distribution plan (source PDFs) |
| [`varuna-graph-fusion/`](varuna-graph-fusion) | **Built.** Person 1's track: the Graph Fusion Engine — see its own [README](varuna-graph-fusion/README.md) for full details, setup, and how to run it |
| [`frontend/`](frontend) | **First pass.** Landing page + an initial 3D digital twin showcase, live-wired to the Graph Fusion Engine's `/fused` endpoint — see its own [README](frontend/README.md) for the design system and how to run it |

The other tracks from the Round-2 work distribution (Drift Memory Engine,
Streaming Backbone/Nowcast, Ocean Model Data Pipeline, Backend API/Real-Time
Layer, In-Situ Data Pipeline, and the full Day-4 production visualization
layer) are owned by teammates and/or not yet built. `varuna-graph-fusion` is
built to plug into them via a documented API contract and adapter pattern
(see its README §5 and §9) so wiring them together on Day 3 is a config
change, not a rewrite; `frontend/` is already live-wired to it the same way.

## System architecture

```
DATA SOURCES          Ocean model (ROMS/HYCOM, NetCDF)  +  Argo/Glider/CTD/Buoy (real readings)
                                        │
INGESTION LAYER        xarray/netCDF parsing, regridding, adapter-per-source
                                        │
INTELLIGENCE LAYER      ① Graph Fusion Engine   <- this repo (varuna-graph-fusion)
   (the differentiator)  ② Drift Memory Engine   <- teammate track
                          ③ Nowcast Engine (stretch) <- teammate track
                                        │
API LAYER               REST (/model /observations /fused /alerts) + WebSocket push
                                        │
VISUALIZATION LAYER      CesiumJS/Three.js: 3D ocean surface, trust overlay,
                          time-scrubber, live alert feed, expert/public mode
```

## Sprint plan (Sept 5–8, 4-day core build)

Per [`Problem_approach/Varuna_67_WD.pdf`](Problem_approach/Varuna_67_WD.pdf):
6 people, 6 parallel tracks, everyone builds against an agreed API contract
from Day 1 so nobody blocks anybody. UI/visualization is intentionally not
touched until Day 4 — the backend + intelligence loop must work end-to-end
(testable via curl/Postman) first.

- **Day 1 (Sept 5):** contracts + scaffolding — lock the JSON shape of all 4
  endpoints, confirm region (Bay of Bengal) and the variable set.
- **Day 2 (Sept 6):** real data starts replacing mocks.
- **Day 3 (Sept 7):** full integration, no UI yet — real model data → real
  in-situ data → Graph Fusion → Drift Memory → alerts, all testable via
  curl/Postman.
- **Day 4 (Sept 8):** frontend blitz + record + rehearse.

**Person 1 / Graph Fusion Engine (this repo) status:** Days 1–2 complete —
graph structure designed, GNN + training-free fallback correction both
running end-to-end against mock data, `/fused` live and tested (50 passing
tests). Since Person 4/6 haven't started their real pipelines yet, extra
Day 2 time went into de-risking Day 3 ahead of schedule: resilient per-point
parsing, physical-plausibility sanitization against QC/sentinel values, and
content-hash caching so repeated `/fused` calls don't retrain the GNN
unnecessarily. Ready to wire to Person 4's real `/model` and Person 6's real
`/observations` the moment they're up — see
[`varuna-graph-fusion/README.md` §9](varuna-graph-fusion/README.md#9-wiring-in-real-data-day-3)
and the handoff checklist,
[`varuna-graph-fusion/DAY3_INTEGRATION.md`](varuna-graph-fusion/DAY3_INTEGRATION.md).

## Quick start

**Backend (Graph Fusion Engine):**

```powershell
cd varuna-graph-fusion
.\scripts\setup_env.ps1
python -m pytest -q                 # 50 tests
python scripts/run_demo.py          # end-to-end CLI demo
uvicorn graph_fusion.api:app --reload --port 8000   # live API
```

**Frontend** (in a second terminal, backend running first for live data):

```powershell
cd frontend
npm install
npm run dev
```

Full details: [`varuna-graph-fusion/README.md`](varuna-graph-fusion/README.md)
· [`frontend/README.md`](frontend/README.md)
