# VARUNA — Drift Memory Engine (Intelligence Core #2)

**Track:** Person 2  
**Role:** Intelligence Core #2 Owner  
**SIH Problem ID:** SIH26067  
**Theme:** Disaster Management / Smart Automation (Ministry of Earth Sciences)  
**Deliverable:** `/alerts` and rolling test-time memory state across Bay of Bengal sub-basins

---

## 1. Overview

The **Drift Memory Engine** flags model-vs-reality divergence in real time. While the Graph Fusion Engine (Person 1) corrects the spatial model grid using oceanographic connectivity, the Drift Memory Engine tracks the **temporal and spatial divergence ("surprise")** between forecast models and real-world ground truth observations.

It is inspired by **Titans: Learning to Memorize at Test Time**. Rather than relying on simple static thresholds that trigger false alarms on noisy sensor pings, it maintains a continuous, rolling memory of model bias per sub-basin and variable, dynamically accelerating its adaptation when an acute shock (e.g. Marine Heatwave) is detected.

```
       [Version A: Model Grid]          [Version B: In-Situ Observations]
       (Person 4: xarray/NetCDF)         (Person 6: Argo / Buoy Adapters)
                  │                                     │
                  └──────────────┬──────────────────────┘
                                 │
                     ┌───────────▼────────────┐
                     │  Graph Fusion Engine   │ (Person 1)
                     │        (/fused)        │
                     └───────────┬────────────┘
                                 │
                     ┌───────────▼────────────┐
                     │  DRIFT MEMORY ENGINE   │ ◄─── Person 2 (This Package)
                     │       (/alerts)        │      Intelligence Core #2
                     └───────────┬────────────┘
                                 │
                     ┌───────────▼────────────┐
                     │  Backend & WebSockets  │ (Person 5)
                     │     (/ws/alerts)       │
                     └───────────┬────────────┘
                                 │
                     ┌───────────▼────────────┐
                     │  3D CesiumJS Frontend  │ (Day 4 Blitz: Alert Feed &
                     │   Trust & Alert Panel  │  Confidence Map)
                     └────────────────────────┘
```

---

## 2. Mathematical Design

### A. Normalized Surprise ($S_t$)
- **Scalar Discrepancy (SST, Wave Height, Salinity):**
  $$e_t(x, y) = y_{\text{obs}}(x, y) - \hat{y}_{\text{model}}(x, y)$$
- **Current Vector Magnitude & Shear Deviation:**
  $$\Delta V = \|\vec{V}_{\text{obs}}\| - \|\vec{V}_{\text{model}}\|$$
  $$\Delta \theta = \arccos\left(\frac{\vec{V}_{\text{obs}} \cdot \vec{V}_{\text{model}}}{\|\vec{V}_{\text{obs}}\| \|\vec{V}_{\text{model}}\| + \epsilon}\right)$$
- **Standardized Innovation:**
  $$S_t = \frac{|e_t|}{\sigma_v}$$
  where $\sigma_{\text{SST}} = 0.50^\circ\text{C}$, $\sigma_{\text{current}} = 0.20\text{ m/s}$, $\sigma_{\text{wave}} = 0.35\text{ m}$.

### B. Test-Time Memory State Update ($M_t$)
$$M_t = (1 - \alpha_t) M_{t-1} + \alpha_t \cdot e_t$$
- Baseline momentum: $\alpha = 0.20$.
- **Adaptive Surprise Boost:** If $S_t \ge 2.5\sigma$, $\alpha$ scales up to $0.85$ to capture sudden regime shifts (e.g. onset of an intense Marine Heatwave).

### C. Severity Tiers

| Severity | SST Divergence | Current Velocity / Shear | Standardized Surprise | Operational Event |
|---|---|---|---|---|
| **INFO** | $0.60^\circ\text{C} \le \|\Delta T\| < 1.20^\circ\text{C}$ | $0.18 \le \Delta V < 0.40\text{ m/s}$ | $1.2 \le S_t < 2.0$ | Localized model drift / minor variance |
| **WARNING** | $1.20^\circ\text{C} \le \|\Delta T\| < 2.00^\circ\text{C}$ | $0.40 \le \Delta V < 0.75\text{ m/s}$ or $\Delta \theta > 45^\circ$ | $2.0 \le S_t < 3.5$ | Boundary current shear / warm anomaly |
| **CRITICAL** | $\|\Delta T\| \ge 2.00^\circ\text{C}$ | $\Delta V \ge 0.75\text{ m/s}$ or $\Delta \theta > 90^\circ$ | $S_t \ge 3.5$ | **Marine Heatwave (MHW)** / Flow reversal |

---

## 3. Sub-Basin Spatial Partitioning

The Bay of Bengal domain ($5^\circ\text{N}-22.5^\circ\text{N}$, $79.5^\circ\text{E}-98.5^\circ\text{E}$) is partitioned into 5 key oceanographic sub-basins:
1. `north_bob` ($18.0^\circ-22.5^\circ\text{N}$): River runoff zone, shallow bathymetry, cyclone landfall.
2. `central_bob` ($13.0^\circ-18.0^\circ\text{N}$): Open basin, mesoscale eddy generation.
3. `south_bob` ($5.0^\circ-13.0^\circ\text{N}$): Sri Lanka Dome, equatorial wave entrance.
4. `andaman_sea` ($6.0^\circ-15.0^\circ\text{N}$, $>92^\circ\text{E}$): Marginal basin, internal solitary wave activity.
5. `coastal_east_india` ($10.0^\circ-20.0^\circ\text{N}$, $<85^\circ\text{E}$): East India Coastal Current (EICC) boundary jet.

---

## 4. API Endpoints

The service runs on **port 8002** (configurable via `VARUNA_DRIFT_PORT`):

- **`GET /health`** — Health check, sub-basin registry, active scenario.
- **`GET /alerts`** — Return active `Alert` models for Person 5's REST/WebSocket proxy and the CesiumJS alert panel.
  - Supports query parameter `?scenario=nominal|marine_heatwave|boundary_current_shear|compound_anomaly`
  - Supports query parameter `?use_upstream=true` (queries Person 1's live `/fused` endpoint).
- **`GET /memory/state`** — Diagnostic inspection of rolling memory cells across all sub-basins.
- **`POST /scenario/{name}`** — Dynamically switch demo scenario.
- **`POST /evaluate/fused`** — Evaluate drift directly on a `FusedResponse` payload.
- **`POST /evaluate/raw`** — Evaluate drift directly on paired `ModelSnapshot` and `ObservationSnapshot`.
- **`POST /reset`** — Clear memory cells and reset debounce caches.

---

## 5. Quickstart

### Running the API
```powershell
# From drift-memory-engine directory:
python -m uvicorn drift_memory.api:app --reload --port 8002
```

### Running Tests
```powershell
python -m pytest
```
