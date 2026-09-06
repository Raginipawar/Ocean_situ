# VARUNA — frontend

**SIH26067 · Team Hudson Hackers · Ministry of Earth Sciences (Disaster Management)**

The public site + Digital Twin dashboard for VARUNA (Visualization & Assimilation
of Real-time Underwater Network Analytics) — a browser-based living digital twin
of the Bay of Bengal that fuses INCOIS forecast data with real Argo/glider/CTD/buoy
readings and flags where the model and reality disagree.

This is the **Day 4 frontend blitz** deliverable (Person 1 / UI-UX Lead's track,
per `../Problem_approach/UI_UX_TESTING PART_WD.pdf`), rebuilt from scratch on
2026-09-06. It talks to the real, already-built backend at
[`../varuna-graph-fusion`](../varuna-graph-fusion) — nothing on this site is a
disconnected mock dressed up as a feature.

---

## 1. Quick start

```powershell
# from Ocean_situ/frontend
npm install
npm run dev        # http://localhost:5173
```

The Digital Twin page (`/digital-twin`) needs the backend running in a second
terminal, or it will show an honest "can't reach the backend" banner instead of
fabricated data:

```powershell
# from Ocean_situ/varuna-graph-fusion
.\scripts\setup_env.ps1
uvicorn graph_fusion.api:app --reload --port 8000
```

Other scripts:

```powershell
npm run build     # type-check (tsc -b) + production build to dist/
npm run preview   # serve the production build locally
npm run lint      # oxlint
```

To point the frontend at a different backend URL (e.g. a deployed API), copy
`.env.example` to `.env.local` and set `VITE_API_BASE_URL`.

---

## 2. Design system

### Where the direction came from

The brief was richardsancho.com's typography/gradient feel — a huge condensed
display headline, a wide grotesque nav face, warm near-monochrome palette — with
the header layout adapted to VARUNA's own needs (wordmark pinned top-left,
services nav pinned top-right), plus a rotating 3D-style globe in the hero in the
spirit of earth3dmap.com and the Framer "free 3D earth globe" marketplace
component (drag-rotate, atmosphere glow, starfield, pulse markers).

**Font-licensing note:** richardsancho.com's actual headline faces are
*Roslindale Display Condensed* and *GT America Extended* — both paid, commercial
fonts (Displaay / Grilli Type). Those aren't shipped here; this project pairs
free, equivalent-personality Google Fonts instead so there's no licensing risk
on an official government-facing entry:

| Role | Font | Stands in for |
|---|---|---|
| Display headlines (`.font-display`) | **Big Shoulders Display** | Roslindale Display Condensed |
| Nav / labels / UI chrome (`.font-nav`) | **Archivo Expanded** | GT America Extended |
| Body copy, quotes (default serif) | **EB Garamond** | Same font richardsancho.com actually uses — free already |
| Coordinates, stats, code (`.font-mono-data`) | **JetBrains Mono** | — |

All four are loaded via Google Fonts in `index.html`. Font tokens live in
`src/index.css` under `@theme` (`--font-display`, `--font-sans`, `--font-serif`,
`--font-mono`).

### Color & the "gradient effect"

richardsancho.com's gradient isn't a static CSS gradient — it's a click-triggered
WebGL colour wash (Three.js + Tone.js) that only appears after visitor
interaction. That's a fun gimmick for a personal portfolio but wrong for a
judge-facing / official site where the wow-factor needs to be visible on first
paint. `.gradient-wash` in `src/index.css` is the practical translation: a
slow-drifting radial-gradient mesh in ocean teal → navy, always visible,
respecting `prefers-reduced-motion`.

Palette (CSS custom properties, redefined per theme):

| Token | Light | Dark |
|---|---|---|
| `--color-bg` | `#f4eae1` (richardsancho's exact cream) | `#06090c` |
| `--color-ink` | `#14110f` | `#f4eae1` |
| `--color-accent` | `#0f6e63` (ocean teal) | `#35b8a6` |
| `--color-accent-2` | `#143a5c` (deep navy) | `#5c9be0` |
| `--color-trust-green/amber/red` | matches backend thresholds | brighter for dark bg |

**Trust colors are semantic, not decorative** — they map 1:1 to the backend's
real `trust_label` values (see §4) and should never be reused for anything else.

### Light / dark mode

A real toggle (`src/theme/ThemeProvider.tsx`), not just
`prefers-color-scheme` — it initializes from the OS preference, then persists
the user's explicit choice to `localStorage` (`varuna-theme`) and applies it via
a `.dark` class on `<html>`. Tailwind v4's CSS-first dark variant
(`@custom-variant dark`) is wired to that class in `src/index.css`.

### Motion

GSAP + ScrollTrigger (free, MIT since the 2024 Webflow acquisition) power
scroll-triggered reveals via the `<Reveal>` component
(`src/components/Reveal.tsx`) — the same library richardsancho.com itself uses.
Everything respects `prefers-reduced-motion`.

### The globe

`src/components/globe/Globe.tsx` is a **hand-built** rotating orthographic globe
— not an embed, not a paid component (Vectary was suggested as inspiration but
is a hosted 3D editor, not something that can bind to live backend coordinates;
MagicUI's `cobe`-based globe was also considered but this needed direct control
over region-bbox overlays and per-point trust colouring driven by real API data).

Built with `d3-geo` (orthographic projection, graticule) +
`topojson-client`/`world-atlas` (Natural Earth 110m land + country borders,
public domain data, MIT-licensed npm package — see
`src/assets/geo/countries-110m.json`). Features:

- Drag-to-rotate (pointer events, no external gesture library)
- Idle auto-rotation that pauses on interaction and resumes after 1.8s
- Atmosphere glow, starfield-free minimalist styling (kept light — no external
  starfield image assets)
- Optional `regionBBox` prop that draws VARUNA's real scope-locked Bay of
  Bengal bounding box (5–22°N, 80–100°E, from `graph_fusion/config.py`) as a
  highlighted region — used on the Home hero
- Optional `markers` prop, each with a `color` — used on the Digital Twin page
  to plot real `/fused` sensor-anchored points colored by their actual
  `trust_label`

No literal sensor coordinates are hard-coded anywhere as if they were live —
the Home hero shows the *region*, not fake sensor pins; only the Digital Twin
page plots points, and only once the real backend has returned them.

---

## 3. Folder structure

```
frontend/
├── index.html                  Fonts, meta, title
├── .env.example                VITE_API_BASE_URL
├── src/
│   ├── main.tsx                Mounts <App> inside <ThemeProvider>
│   ├── App.tsx                 Router + lazy-loaded routes
│   ├── index.css               Tailwind v4 import, theme tokens, gradient wash
│   ├── vite-env.d.ts
│   ├── lib/
│   │   ├── types.ts            Mirrors graph_fusion/schemas.py exactly
│   │   ├── config.ts           Mirrors graph_fusion/config.py (region, thresholds)
│   │   ├── api.ts              Typed fetch client — no client-side mock fallback
│   │   └── gsap.ts             Registers ScrollTrigger once
│   ├── theme/
│   │   └── ThemeProvider.tsx   Light/dark context + localStorage persistence
│   ├── components/
│   │   ├── Nav.tsx             VARUNA wordmark (left) + nav + theme toggle (right)
│   │   ├── Footer.tsx
│   │   ├── Reveal.tsx          GSAP ScrollTrigger fade-up wrapper
│   │   ├── TrustBadge.tsx      Renders a real TrustLabel as a colored pill
│   │   ├── CoordinateReadout.tsx  Live lat/lon readout (mono font)
│   │   └── globe/
│   │       └── Globe.tsx       The hand-built d3-geo orthographic globe
│   ├── pages/
│   │   ├── Home.tsx            Hero, "the gap", architecture, why-now, CTA
│   │   ├── Services.tsx        Engines, data sources, real API contract
│   │   ├── About.tsx           Team, PS details, delivery timeline
│   │   └── DigitalTwin.tsx     Live shell wired to /health /model /observations /fused
│   └── assets/
│       └── geo/countries-110m.json   Natural Earth 110m topology (world-atlas)
└── public/
    └── favicon.svg
```

---

## 4. Backend contract this frontend actually talks to

Mirrors `../varuna-graph-fusion/src/graph_fusion/{api,schemas,config}.py`
exactly — if the backend contract changes, update `src/lib/types.ts` and
`src/lib/config.ts` only; every component imports from there.

| Endpoint | Returns |
|---|---|
| `GET /health` | `{ status, region }` |
| `GET /model` | `ModelSnapshot` — Version A (simulated ocean) grid points |
| `GET /observations` | `ObservationSnapshot` — Version B (real sensor) points |
| `GET /fused?engine=auto\|gnn\|fallback` | `FusedResponse` — corrected points with `confidence`, `trust_label` (`green`/`amber`/`red`), `is_sensor_node`, plus a `FusionSummary` |
| `WS /alerts` | **Not yet exposed by the API** — belongs to the Drift Memory Engine track. The Digital Twin page's alert panel says so honestly instead of showing a fabricated feed. |

Trust thresholds (from `config.py`, rendered as a legend on the Digital Twin
page): **green ≥ 70% confidence, amber ≥ 40%, red below 40%.** The frontend
never re-derives this client-side — it only ever displays the `trust_label`
the backend already computed.

Region scope lock: **Bay of Bengal**, `lat 5–22°N`, `lon 80–100°E`,
region key `bay_of_bengal` — `src/lib/config.ts`.

---

## 5. What's real vs. what's a placeholder

Being explicit about this so nobody — teammate or judge — mistakes one for the
other:

- **Real and live:** everything on `/digital-twin` once the backend is running
  — `/health`, `/model`, `/observations`, `/fused` are genuinely fetched, and
  the trust colors/confidence numbers shown are the backend's actual GNN/
  fallback output, not sample data.
- **Real and static:** all copy on Home/Services/About is drawn directly from
  `../Problem_approach/SIH_67_APPROACH.pdf` and the work-distribution docs —
  the architecture layers, the competitive table, the "why now" citations, the
  delivery timeline, the PS metadata.
- **Honestly not built yet:** the live alert feed (`/alerts` — Drift Memory
  Engine track) and the full CesiumJS draped-ocean-surface 3D scene described
  in the approach doc's Visualization Layer. The Digital Twin page today
  renders fused points on the lightweight `Globe` component plus a data table
  as an interim, real-data view — swapping in the full CesiumJS scene (owned
  by Person 4 per the work-distribution doc) is the next build step, not a
  hidden gap.
- **Marked "Future Scope" on purpose:** the Nowcast Engine, per the team's own
  risk/fallback plan — it's presented as a roadmap item, never as a shipped
  feature.

---

## 6. Tech stack

- **React 19 + TypeScript + Vite** (scaffolded via `npm create vite@latest -- --template react-ts`)
- **Tailwind CSS v4** (CSS-first config via `@theme`/`@custom-variant` in `index.css`, `@tailwindcss/vite` plugin — no `tailwind.config.js` needed)
- **React Router** for the four pages, with `Services`/`About`/`DigitalTwin` code-split via `React.lazy`
- **GSAP + ScrollTrigger** for scroll reveals
- **d3-geo + topojson-client + world-atlas** for the hero/dashboard globe
- **oxlint** for linting (already configured by the Vite scaffold)

No CesiumJS dependency yet — it's a heavy engine reserved for the real
draped-ocean-surface Digital Twin scene described in §5, to keep the marketing
pages fast in the meantime.

---

## 7. Known limitations / next steps

- Digital Twin's 3D view is the lightweight `Globe` component, not the full
  CesiumJS scene from the approach doc's Visualization Layer yet.
- No `/alerts` WebSocket wiring — waiting on the Drift Memory Engine track.
- No automated test suite yet (Vitest + React Testing Library would be the
  natural fit given the Vite setup, if time allows before the demo).
- Main JS bundle is ~490KB (mostly React + GSAP + d3-geo) — acceptable for a
  hackathon demo; further code-splitting (e.g. lazy-loading `Globe` itself)
  is the obvious next lever if load time becomes a concern.
