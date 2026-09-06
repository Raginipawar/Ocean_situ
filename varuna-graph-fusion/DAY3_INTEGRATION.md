# Day 3 integration checklist

**For:** Person 4 (`/model` owner) and Person 6 (`/observations` owner)
**From:** Person 1 (Graph Fusion Engine)
**Status as of Sept 6 (Day 2 evening):** neither real pipeline has started
yet — this is prep, done ahead of time so wiring you in on Day 3 is a
5-minute config change, not a debugging session.

## The contract your endpoint needs to match

Full machine-readable spec: [`src/graph_fusion/schemas.py`](src/graph_fusion/schemas.py)
(`ModelSnapshot`/`ModelGridPoint` for `/model`, `ObservationSnapshot`/
`ObservationPoint` for `/observations`). Human-readable summary:

**`/model`** (GET, returns one snapshot):
```jsonc
{
  "region": "bay_of_bengal",
  "time": "2026-09-07T10:00:00Z",
  "resolution_deg": 1.0,
  "source": "INCOIS-LAS",           // or "copernicus-glorys", etc.
  "points": [
    { "lat": 13.0, "lon": 88.0, "depth_m": 0.0,
      "sst_c": 28.4, "current_u_ms": 0.12, "current_v_ms": -0.05, "wave_height_m": 1.1 }
    // ...
  ]
}
```

**`/observations`** (GET, returns one snapshot):
```jsonc
{
  "region": "bay_of_bengal",
  "time": "2026-09-07T10:00:00Z",
  "source": "argovis",
  "points": [
    { "sensor_id": "argo-2903412", "sensor_type": "argo",
      "lat": 13.05, "lon": 87.98, "depth_m": 0.0, "time": "2026-09-07T09:58:00Z",
      "sst_c": 30.1, "current_u_ms": null, "current_v_ms": null, "wave_height_m": null }
    // ...
  ]
}
```

`sensor_type` accepts: `argo`, `glider`, `ctd`, `buoy`, `mooring`, `hf_radar`,
`adcp`, `drifter`, `xbt`. Any measurement field can be `null` (a CTD doesn't
report currents, etc.) — that's expected and handled.

**If your real payload shape genuinely differs** (different field names,
nested structure, whatever your actual data source hands you), tell me and
we update `schemas.py` together — every other module in this package only
ever talks to the system through those types, so that's the *only* file
that needs to change.

## How to flip the switch (my side, already built)

```powershell
$env:VARUNA_MODEL_SOURCE = "http"
$env:VARUNA_MODEL_SOURCE_URL = "http://<your-host>:<port>/model"
$env:VARUNA_OBS_SOURCE = "http"
$env:VARUNA_OBS_SOURCE_URL = "http://<your-host>:<port>/observations"
uvicorn graph_fusion.api:app --reload --port 8000
```

Then `curl http://localhost:8000/fused` should return real, fused data.

## What I've already hardened, so your real feed doesn't need to be perfect

Real sensor/model feeds are messy in predictable ways. Rather than asking
you to guarantee clean data, the engine now handles the messy cases itself:

1. **One bad reading doesn't kill the whole batch.** A single malformed
   point (bad GPS fix, missing field, a `sensor_type` we haven't enumerated)
   used to fail the *entire* `/model` or `/observations` response — one
   flaky sensor could 500 the whole endpoint. Now it's dropped and logged,
   everything else still comes through (`src/graph_fusion/ingest.py`).
2. **QC fill values and physically-impossible readings are filtered before
   fusing**, not treated as real (`src/graph_fusion/sanitize.py`) — common
   sentinels like `-999`/`-9999`, and anything outside a wide physical
   sanity range (SST outside -2°C to 40°C, etc.), become "no reading"
   rather than a real value that would produce a wildly wrong correction.
   Verified live: a sensor sending `-999` for SST does **not** produce a
   ~1000°C bogus correction — it either falls back to the model's own value,
   or (if a real neighboring sensor exists) gets a sensible graph-propagated
   estimate instead.
3. **Repeated identical requests don't retrain the GNN every time**
   (content-hash cache in `fusion_service.py`) — matters once your feed is
   live and something (a dashboard poll, a frontend refresh) hits `/fused`
   repeatedly; only a genuinely new reading triggers real recomputation.

## Timestamp handling (read before Day 3)

The engine does **not** currently check that `/model.time` and
`/observations.time` are close together — it fuses whatever it's given,
regardless of how stale either snapshot is. That's fine for correctness
(the math doesn't care), but if your model snapshot is 6 hours stale and
observations are live, the "disagreement" the trust overlay shows will
partly just be *forecast drift*, not model-vs-reality error. Worth agreeing
on a max acceptable staleness window before the demo, even if we don't
enforce it in code.

## Contact points if something doesn't line up

- Wrong field names / shape → edit `schemas.py` together, nothing else changes.
- New sensor type not in the enum → tell me, one-line addition.
- Values look sane in your source but come through as `null` in `/fused` →
  probably `sanitize.py`'s physical range being too tight for a real edge
  case (e.g. an actual marine heatwave briefly exceeding 40°C) — tell me and
  we widen it.
