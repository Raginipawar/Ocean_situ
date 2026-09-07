# VARUNA — Streaming Backbone + Nowcast Engine

**SIH26067 · Team Hudson Hackers · Person 3 / Intelligence Core #3 (stretch goal)**

This track owns two things: the **Streaming Backbone** (the real-time
ingestion state-update logic every other track's "live" framing depends on)
and the **Nowcast Engine** (an optional short-range ocean-state prediction,
attempted only if the backbone is solid — see
[`../raw info/Person3_Detailed_Work_Brief.md`](../raw%20info/Person3_Detailed_Work_Brief.md)
for the full day-by-day brief this track was built against).

**Status: both are done, and the Nowcast Engine went further than the
brief's own "stretch, honest attempt" bar asked for** — it's trained on
**real Copernicus Marine data** (not synthetic sequences), predicts a
genuine **3D volume** (depth × lat × lon, not just a surface grid), and
beats a persistence baseline on real held-out test data. See
[§4](#4-nowcast-engine-results-real-data) for numbers.

---

## 1. Streaming Backbone

`src/streaming_nowcast/streaming_backbone.py`: a from-scratch, ~20-line LSTM
state-update function (`lstm_state_update`) — no `torch.nn.LSTM`, so every
gate is readable line-by-line, matching the work brief's "must be able to
explain and defend every part of the system" rule. Wrapped by
`StreamingBackbone`, which:

- ingests one reading at a time (`ingest()`), a burst of several at once
  (`ingest_batch()`), or a gap (`ingest(None)`) — state persists unchanged
  through a gap rather than crashing or hallucinating a fabricated reading;
- sanitizes NaN/None fields in a reading without poisoning the whole update;
- raises loudly (`FloatingPointError`) if state ever diverges to NaN/Inf,
  rather than silently producing garbage.

CPU-only, no compiled extensions — the work brief's Section 11 explicitly
rules out `mamba-ssm` (the architecture's eventual target-state design; see
[§6](#6-the-mambassm-question)), and this backbone is the honest, dependency-light
stand-in.

`src/streaming_nowcast/mock_stream.py` generates the streaming demo data —
anchored in **real** spatial structure (Person 4's model-pipeline output,
via `real_data.py`) rather than an invented formula, with realistic sensor
noise and a small simulated temporal drift layered on top (no track has a
real *time-series* sensor feed yet — that's this component's own job to
demonstrate). Injects gaps and bursts on configurable probabilities (Task
2.3's stress-test requirement).

## 2. Nowcast Engine — architecture

`src/streaming_nowcast/convlstm.py`: a from-scratch **stacked ConvLSTM**
(Shi et al. 2015 lineage — the precipitation-nowcasting architecture the
work brief specifies, not the JEPA-based version from the original draft).
Every gate is a `nn.Conv3d` over `(depth, lat, lon)` volumes rather than a
flat vector or a 2D surface grid — genuinely volumetric, so a predicted
"warm patch" has real depth structure, not just a colored pixel.

Predicts a **residual** (the change from the last observed volume), not the
raw next state — see the module docstring for why: ocean fields sit at a
large, near-constant value that barely moves frame to frame, so a freshly
initialized network predicting the raw value from scratch would spend most
of training just learning the offset. Residual prediction starts at
persistence-level accuracy for free.

CPU-only stock ops (`nn.Conv3d`, same portability guarantee as Section 11) —
but *training* defaults to GPU when available (`torch.cuda.is_available()`)
since training speed doesn't affect the delivered artifact: a GPU-trained
checkpoint loads and runs inference on CPU identically. See
`NowcastEngine`'s docstring in `nowcast_engine.py`.

## 3. Real data — not synthetic

No track had real *time-series* gridded ocean data when this began (Person
4's pipeline gives one static real snapshot; nobody has a multi-day feed).
Rather than simulate one, this track gathered **genuine Copernicus Marine
data** directly:

| Variable | Source | Real range |
|---|---|---|
| SST, Salinity, Currents (u/v) | `GLOBAL_MULTIYEAR_PHY_001_030` (GLORYS reanalysis) | Daily, 270 real consecutive days (1 Jan – 27 Sep 2023, two fetches concatenated), 0–56m depth |
| Wave height | `GLOBAL_MULTIYEAR_WAV_001_032` (Waves Reanalysis) | 3-hourly, 2022–2026, averaged to daily |
| Chlorophyll | `GLOBAL_MULTIYEAR_BGC_001_029` (Biogeochemistry Hindcast) | Monthly (native product cadence), held constant across days in the same real month |

The 270-day window spans a real season transition (calm pre-monsoon into
monsoon onset) — deliberately not cherry-picked for a calmer, easier-to-predict
stretch; see [§4](#4-nowcast-engine-results-real-data) for what that costs the score,
honestly.

`src/streaming_nowcast/real_ocean_data.py` regrids every variable onto one
shared spatial grid and depth-level set (own, direct `xarray.interp` per
variable — **not** `varuna_model_pipeline`'s `regrid_to_target`, which was
found, while building this, to intermittently return non-deterministic
garbage values via its combined multi-dimension `.interp()` call; reported
back, not silently worked around — see the module's docstring).

Land cells (~30% of this Bay-of-Bengal box — real coastline: India, Sri
Lanka, Myanmar, Bangladesh) are masked out of every loss and metric, never
zero-filled and silently "learned" as correct ocean physics.

`src/streaming_nowcast/synthetic_ocean.py` remains as a **fallback only** —
`NowcastEngine.train()` uses it automatically if no real file paths are
given, so the package still runs standalone for anyone without the (large,
not-committed-to-git) real files.

## 4. Nowcast Engine results (real data)

Trained on real Copernicus Marine data, chronological train/val/test split
(earliest real days → train, next block → validation, latest → test — never
random-shuffled, so the model is never evaluated on something chronologically
"before" what it trained on), per-channel normalization fit on training-split
ocean cells only, masked loss, early stopping with best-checkpoint selection.

**Primary result — full 270-day real dataset, stacked 2-layer ConvLSTM (202,518 params), GPU-trained:**

| | |
|---|---|
| Variables predicted | SST, Salinity, Current-U, Current-V, Wave height, Chlorophyll — all 6 |
| Grid | 0.25° × 0.25°, 10 real depth levels (surface to ~56m) |
| Held-out test MSE (model) | 0.0539 (normalized units) |
| Held-out test MSE (persistence baseline) | 0.0617 |
| **Improvement over persistence** | **12.6%** |
| SST channel, held-out prediction | mean absolute error **0.113 °C** |
| Best epoch / early-stopped at | epoch 22 / 52 (val loss stopped improving; training curve in `results/nowcast_loss_curve.png` is clean, no runaway overfitting) |

Honest note on this number: an earlier run on a *calmer* 90-day window
(Jan–Mar, pre-monsoon, single ConvLSTM layer) scored **16.2%** improvement —
higher, not lower. The 270-day run isn't a strictly "better" model in every
sense; it's evaluated on a genuinely harder, more realistic test set (the
window spans real monsoon transition, where ocean state is intrinsically
less persistent/predictable), trained on 3x more real data and a deeper
model. Both numbers are real, reproducible, and kept rather than only
reporting the more flattering one.

See `results/` for the full evidence trail: `nowcast_loss_curve.png` (clean
convergence, best-checkpoint correctly selected before the noisier later
epochs), `nowcast_sst_surface_comparison.png` and
`nowcast_multi_channel_summary.png` (predicted vs. actual, all 6 variables —
real Bay of Bengal coastline visible in the land mask, real mesoscale
structure preserved in the prediction, not just a smoothed blob),
`nowcast_metrics.json`, and `nowcast_model.pt` (the trained checkpoint,
CPU-loadable regardless of the GPU it trained on).

Per Section 7 Task 3.C's three honest outcomes for the Nowcast Engine
(working / partial-with-caveats / documented Future Scope): this is
**state 1 — working and demoable**, on real data, with an evidence trail.

## 5. Integration contracts

`src/streaming_nowcast/schemas.py` mirrors `/model`/`/observations` (so this
package is independently runnable without importing another track's
package) and owns two new types:

- `StreamingState` — the backbone's live state, for demo/logging or a future
  hand-off through Person 5's API (this track does not own endpoints).
- `NowcastSnapshot`/`NowcastGridPoint` — the optional hand-off contract to
  Person 2's Drift Memory (a second comparison signal) or the frontend, per
  Section 12 of the work brief. Not a committed contract — only wired in if
  the team decides it's worth it.

`src/streaming_nowcast/grid_utils.py` converts between this flat point-list
shape and the 2D/3D grid the ConvLSTM operates on.

**Contribution to Person 4's `model-pipeline`:** his `sources/glorys.py`
explicitly deferred live Copernicus authentication ("intentionally outside
this checkpoint"). `../model-pipeline/src/varuna_model_pipeline/sources/glorys_live.py`
is that missing piece — own file, own tests, doesn't touch his tested
parsing logic (see its docstring) — and it is now **wired into his active
source-selection flow**, not just sitting alongside it: when no local GLORYS
fallback file is given and `ModelPipelineSettings.use_live_glorys_fallback`
is set (off by default — it needs network access and a prior
`copernicusmarine login`), `source_selection.py` calls it to fetch a fresh
real window and uses that as the fallback automatically. That means Person
1's Graph Fusion Engine (or anyone consuming `model-pipeline`'s output) can
get real, live Copernicus data through the exact same `/model` path it
already uses, by flipping one config flag — no separate integration step.
See `../model-pipeline/README.md`'s "Live GLORYS Fetch" section for the
wiring details and how to turn it on.

## 6. The Mamba/SSM question

The architecture diagram shows Mamba (a State-Space Model) as the
target-state design for the Streaming Backbone — a modern, efficient
alternative to recurrent networks for long sequences, staged for the
December finals build if GPU access is available then. **This build does
not use it.** `mamba-ssm` requires custom CUDA kernels with a confirmed open
build issue on native Windows, and needs an NVIDIA GPU regardless of OS —
a real, already-identified risk this team explicitly chose not to take on a
4-day timeline. Instead: the same architectural role (continuous state
update over a stream) is filled by the from-scratch LSTM in §1, and this
README documents exactly where Mamba would slot in for the production
version. A legitimate, common engineering practice — prove the pattern with
a lightweight component before committing to a heavier dependency — not
something to present apologetically.

## 7. Quick start

```powershell
cd varuna-streaming-nowcast
.\scripts\setup_env.ps1
python -m pytest tests -q --ignore=tests\test_real_ocean_data.py   # 27 tests, no real data files needed
python scripts\run_demo.py                                         # streaming backbone + synthetic-fallback nowcast demo
```

**Training on real data** (once you have the Copernicus Marine files — see
§3 for exact product IDs, or `copernicusmarine login` + `subset` to fetch
your own):

```python
from streaming_nowcast.nowcast_engine import NowcastEngine
from streaming_nowcast import results

engine = NowcastEngine()  # auto-selects GPU if available, CPU otherwise
history = engine.train(
    phy_path="path/to/glorys_temperature_salinity_currents.nc",  # or a list of files
    wave_path="path/to/wave_height.nc",
    chlorophyll_path="path/to/chlorophyll.nc",
)
evaluation = engine.evaluate()
print(evaluation)  # {"model_mse": ..., "persistence_baseline_mse": ..., "improvement_over_baseline_pct": ...}

results.save_metrics(history, evaluation)
results.plot_loss_curve(history)
engine.save("results/nowcast_model.pt")
```

Full details on every module: read the docstring at the top of each file in
`src/streaming_nowcast/` — each one explains not just what it does but why,
including every deliberate simplification and every bug found and routed
around along the way (grep for "found, while building this track" if you
want the unvarnished list).
