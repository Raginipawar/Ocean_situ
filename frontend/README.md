# VARUNA: frontend

**SIH26067 · Team Hudson Hackers · Ministry of Earth Sciences (Disaster Management)**

The public site + Digital Twin dashboard for VARUNA (Visualization & Assimilation
of Real-time Underwater Network Analytics): a browser-based living digital twin
of the Bay of Bengal that fuses INCOIS forecast data with real Argo/glider/CTD/buoy
readings and flags where the model and reality disagree.

This is the **Day 4 frontend blitz** deliverable (Person 1 / UI-UX Lead's track,
per `../Problem_approach/UI_UX_TESTING PART_WD.pdf`), rebuilt from scratch on
2026-09-06. It talks to the real, already-built backend at
[`../varuna-graph-fusion`](../varuna-graph-fusion). Nothing on this site is a
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

### Typography

| Role | Font | Used for |
|---|---|---|
| Display headlines (`.font-display`) | **Instrument Serif** | Hero headline, section `h2`s, the VARUNA wordmark, step numbers on the architecture cards |
| Everything else (`.font-nav`, body, buttons, tables, badges) | **Inter** | Nav links, body copy, buttons, table text, badges. Falls back to `-apple-system, Segoe UI, Roboto` |
| Coordinates, stats, code (`.font-mono-data`) | System monospace stack | `Menlo, Consolas, Liberation Mono, monospace`. Never a Google Font on purpose |

Both web fonts load via Google Fonts in `index.html`. Font tokens live in
`src/index.css` under `@theme` (`--font-display`, `--font-sans`, `--font-mono`).

The hero headline also carries a `.gradient-text` treatment (an accent-to-accent-2
gradient clipped to the text), the editorial "gradient text" look Instrument
Serif is meant to carry, kept to the one flagship headline rather than applied
to every heading.

**Where the layout direction came from:** richardsancho.com's header pattern
(wordmark pinned top-left, nav pinned top-right) and its scroll-driven motion
via GSAP + ScrollTrigger, the same library used here.

### Color: the ocean palette

Light mode is **white with blue accents**; dark mode is **true black**. Both
draw every accent/ink/border color from the same seven-tone palette, they
just aim it at opposite base colors rather than being two unrelated themes:

| Token | Hex | Light role | Dark role |
|---|---|---|---|
| Celestial Canvas | `#091e39` | ink | raised surface |
| Ambassador Blue | `#0b345a` | accent | (spare) |
| Blueberry Twist | `#21567c` | muted ink | (spare) |
| Borage | `#4c81a3` | accent-2 | (spare) |
| Afloat | `#79a4c0` | (spare) | accent |
| Angel Falls | `#a3bed3` | (spare) | muted ink / accent-2 |
| Sea Drive | `#c0d2e0` | raised surface | ink |

`--color-bg` is `#ffffff` in light mode and `#000000` in dark mode, both
outside the seven-tone palette on purpose: the palette supplies the ink,
accents, and the raised/card surface, not the page base.

**Trust colors are semantic, not decorative.** They stay green/amber/red
regardless of theme because they map 1:1 to the backend's real `trust_label`
values (see §4), a safety signal that has to mean the same thing to a
fisherman as it does to a researcher. They deliberately don't follow the blue
palette above.

### Light / dark mode

A real toggle (`src/theme/ThemeProvider.tsx`), not just `prefers-color-scheme`.
It initializes from the OS preference, then persists the user's explicit
choice to `localStorage` (`varuna-theme`) and applies it via a `.dark` class
on `<html>`. Tailwind v4's CSS-first dark variant (`@custom-variant dark`) is
wired to that class in `src/index.css`. The toggle itself is a sun/moon icon
button in the nav (`src/components/Nav.tsx`), not a text label.

The globe's own space backdrop also goes true black in dark mode
(`src/components/globe/Globe.tsx`, `<color attach="background" args=
{["#000000"]} />`, dark mode only) with a procedural starfield, matching the
rest of the page and reading like real Earth-from-orbit photography.

### Glassmorphism

`.glass-bar` in `src/index.css` (backdrop blur + saturate, a hairline border,
a soft shadow) is the one reusable "frosted glass" treatment. There is
exactly **one** fixed header (`src/components/Nav.tsx`) using it, not a stack
of separate bars: wordmark left, page nav + the accessibility icon cluster +
the theme toggle right, all in one row.

### Accessibility toolbar (INCOIS-inspired)

`src/components/AccessibilityBar.tsx` renders inline inside that single
header (it is not its own bar) and mirrors the utility cluster on
[incois.gov.in](https://incois.gov.in/site/index.jsp), left to right:

- **Text size** (`A-` / `A+`): five steps (87.5% to 137.5%) applied by
  setting `document.documentElement.style.fontSize`, so every `rem`-based
  Tailwind size on the page scales with it. State lives in
  `src/theme/AccessibilityProvider.tsx`, persisted to `localStorage`.
- **High contrast**: a real WCAG-style mode (`.high-contrast` in
  `src/index.css`), pure black background, white text, yellow accents, and
  the decorative gradient wash switched off, independent of light/dark
  theme and layered on top of either one.
- **Sitemap**: links straight to `/sitemap`.
- **Language**: see below.
- **Share**: the Web Share API where available, falling back to copying the
  URL to the clipboard with a brief confirmation.

### Multilingual

A lightweight custom i18n layer (`src/i18n/`), not a full framework, since
the scope here is the site chrome rather than every paragraph of technical
copy. `I18nProvider.tsx` exposes a `t(key)` function that falls back to
English for any untranslated key, and `translations.ts` holds the
dictionaries. The language set is **English, Hindi, Bengali, Marathi,
Gujarati, and Telugu**, covering the nav, the hero headline and pitch, CTAs,
the accessibility toolbar's own labels, and the footer.

**Translation coverage is intentionally partial and should be reviewed
before a real demo or launch.** The non-English strings here are AI-assisted
translations of the highest-visibility text, not a native-speaker pass, and
the deeper technical prose on Services/About stays English-only for now
rather than risk a mistranslated scientific claim on an official,
disaster-management-facing tool. Expanding coverage is a matter of adding
keys to `translations.ts`.

### Sitemap page

`src/pages/Sitemap.tsx` (`/sitemap`), styled after
[incois.gov.in/site/sitemap.jsp](https://incois.gov.in/site/sitemap.jsp): a
plain hierarchical list of every route and, one level deeper, every named
section on that route (the same anchors the in-page nav scrolls to, each
given a `scroll-anchor` class in `src/index.css` so the fixed header doesn't
cover the target on jump).

### Notification ticker + build status (also INCOIS-inspired)

Right after the Home hero: a slim scrolling ticker (`NotificationTicker` in
`Home.tsx`, `.ticker-track` in `index.css`, a plain CSS-keyframe marquee, no
extra library) styled after the notification bar on incois.gov.in. It does
**not** claim to be a live feed. INCOIS's bar shows real dated bulletins;
this project has no live drift alerts yet (`/alerts` isn't built), so
inventing dated bulletins would be exactly the kind of fake content this
whole project has avoided elsewhere. Instead it honestly labels itself "What
VARUNA watches for" and lists the real alert *categories* the Drift Memory
Engine is designed to raise (SST divergence, wave height divergence, current
divergence, cyclone-scale drift), each tied to a real variable in
`graph_fusion/config.py`.

Each ticker item is a real link, not decoration, matching the pattern on
incois.gov.in where clicking a bulletin opens the real advisory behind it.
These open the actual current INCOIS service for that category (verified
`200 OK` at the time of writing): Ocean State Forecast for SST and current
divergence, the High Wave Advisory for wave height divergence, and the Storm
Surge Warning page for cyclone-scale drift.

Immediately below that: the "Build status, honestly" widget (tabs for real
per-engine build status and the real research references, plus a `LiveStatusCard`
that pings the backend's actual `/health` endpoint) — this is this project's
answer to INCOIS's Latest/What's New/Publications tabs and its "Live
Advisories" widget, built from real project state instead of Vacancies/
Tenders/RTI, which don't apply to a hackathon prototype.

### Motion

GSAP + ScrollTrigger power scroll-triggered reveals via the `<Reveal>`
component (`src/components/Reveal.tsx`). Everything respects
`prefers-reduced-motion`.

### The globe

`src/components/globe/Globe.tsx` is a real, photographically-textured 3D
Earth, built with **React Three Fiber** (`@react-three/fiber`) and **drei**
(`@react-three/drei`) on top of Three.js, not an SVG country-outline
approximation and not an embedded third-party widget.

- **Textures:** day map, cloud layer, and a night-lights emissive map at
  `src/assets/textures/`, sourced from
  [Solar System Scope](https://www.solarsystemscope.com/textures/)
  (CC BY 4.0, credited here per the license).
- A Fresnel rim-light shader gives the atmosphere glow around the limb of the
  planet (standard view-angle-based glow technique, not a third-party asset).
- `drei`'s `<OrbitControls>` gives free-rotate dragging with damping and an
  idle auto-rotate, and `<Stars>` renders the starfield procedurally (no
  extra image asset needed).
- `regionBBox` draws VARUNA's real scope-locked Bay of Bengal bounding box
  (5-22°N, 80-100°E, from `graph_fusion/config.py`) as a highlighted outline
  on the sphere, used on the Home hero.
- `markers`, each with a `color`, plot real `/fused` sensor-anchored points
  colored by their actual `trust_label` on the Digital Twin page.

No literal sensor coordinates are hard-coded anywhere as if they were live.
The Home hero shows the *region*, not fake sensor pins; only the Digital Twin
page plots points, and only once the real backend has returned them.

### Signature interactive moments

Four components from [React Bits](https://reactbits.dev) (MIT + Commons
Clause, vendored into `src/components/effects/` and adapted, not installed as
a package) at the moments where an interactive detail earns its place rather
than being sprinkled everywhere:

- **`SplashCursor`** (Home hero only): a WebGL fluid-sim cursor trail, tuned
  down from its flashy rainbow default to a faint, matte dark blue
  (`#0b345a`, `SHADING={false}` to drop the metallic specular look, wrapped
  at 35% opacity), lower resolution for performance, and **adapted to bind
  to its own section instead of the whole viewport** (the original tracks
  the cursor across the entire page via `window`/`document.body` listeners
  and a fixed full-screen canvas; here it reads its own container's
  `getBoundingClientRect()` and ignores pointer input outside it, so it only
  reacts inside the hero, and only mounts at all once the hero is actually
  on screen). Skipped entirely under `prefers-reduced-motion`.
- **`SpecularButton`** (the two primary "Open the Digital Twin" CTAs on
  Home): a WebGL edge-light sweep on hover/proximity, **adapted to add a
  `to` prop** (the original only renders a `<button>` with `onClick`; here,
  when `to` is set, it renders a real react-router `<Link>` through the same
  ref so internal navigation, middle-click, and "open in new tab" keep
  working, not just a JS-driven click handler).
- **`RippleDistortion`** (Home, a full-bleed panel before the closing CTA):
  a real photo of ocean waves that visibly ripples where you hover, grayscale
  with a blue tint matching the current theme's accent color. Already
  respects `prefers-reduced-motion` upstream.
- **`OrbitImages`** (About page, "The region, and the problem"): a slow
  orbiting ring of real photos, **adapted to add `links`/`labels` props** (the
  original renders plain decorative `<img>`s with `aria-hidden` on the
  container; here each image is a real link to its source, and the
  `aria-hidden` was removed since the content is now meaningful/navigable).

All three ship with a short attribution header in their source file pointing
back to the original React Bits component and noting what was changed.
`ogl` (RippleDistortion) and `motion` (OrbitImages) are the only new runtime
dependencies; SplashCursor is self-contained WebGL.

**The images are real, not stock filler**, sourced from Wikimedia Commons
(NASA/NOAA/Ifremer/OOI public-domain work, plus two CC BY/CC BY-SA photos
credited on the About page) and downsized locally before bundling:

| Image | What it is | Links to |
|---|---|---|
| Bay of Bengal relief map | The region VARUNA is scope-locked to | Wikipedia: Bay of Bengal |
| Cyclone Fani (NOAA, 2019) | The kind of extreme event this needs to catch early | Wikipedia: Cyclone Fani |
| Argo float deployment (NOAA) | A real in-situ data source VARUNA fuses in | argo.ucsd.edu |
| INCOIS building | The forecast source VARUNA validates against | incois.gov.in |
| Fishing boats, Puri, Odisha | Who the tool is ultimately for | INCOIS Ocean State Forecast |
| CTD cast (OOI) | Another real sensor type in the data layer | Wikipedia: CTD (instrument) |
| Ocean waves, Mangalore | The `RippleDistortion` source photo | (decorative, not a link) |

The ocean-wave photo for the ripple effect is genuinely Indian coastal water
(CC BY 4.0, Ksheera Piraati), not a random stock wave.

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
│   │   ├── api.ts              Typed fetch client, no client-side mock fallback
│   │   └── gsap.ts             Registers ScrollTrigger once
│   ├── theme/
│   │   ├── ThemeProvider.tsx   Light/dark context + localStorage persistence
│   │   └── AccessibilityProvider.tsx  Font-size steps + high-contrast mode
│   ├── i18n/
│   │   ├── translations.ts     en/hi/te dictionaries + language list
│   │   └── I18nProvider.tsx    Language context, t() with English fallback
│   ├── components/
│   │   ├── Nav.tsx             The one fixed header: wordmark, nav, AccessibilityBar, sun/moon toggle
│   │   ├── AccessibilityBar.tsx  INCOIS-style icon cluster (font size, contrast, sitemap, language, share)
│   │   ├── Footer.tsx
│   │   ├── Reveal.tsx          GSAP ScrollTrigger fade-up wrapper
│   │   ├── TrustBadge.tsx      Renders a real TrustLabel as a colored pill
│   │   ├── CoordinateReadout.tsx  Live lat/lon readout (mono font)
│   │   ├── globe/
│   │   │   └── Globe.tsx       The React Three Fiber realistic Earth
│   │   └── effects/            Vendored + adapted React Bits components (see §2)
│   │       ├── SplashCursor.tsx / .css
│   │       ├── RippleDistortion.tsx / .css
│   │       └── OrbitImages.tsx / .css
│   ├── pages/
│   │   ├── Home.tsx            Hero (+ SplashCursor), "the gap", architecture,
│   │   │                       why-now, RippleDistortion panel, CTA
│   │   ├── Services.tsx        Engines, data sources, real API contract
│   │   ├── About.tsx           Team, PS details, OrbitImages, delivery timeline
│   │   ├── DigitalTwin.tsx     Live shell wired to /health /model /observations /fused
│   │   └── Sitemap.tsx         Hierarchical page list, INCOIS sitemap.jsp-style
│   └── assets/
│       ├── textures/           Earth day/night/clouds JPGs (Solar System Scope, CC BY 4.0)
│       ├── effects/             Ocean-wave photo for RippleDistortion (CC BY 4.0)
│       └── orbit/               Six real photos for OrbitImages (see §2 credits)
└── public/
    └── favicon.svg
```

---

## 4. Backend contract this frontend actually talks to

Mirrors `../varuna-graph-fusion/src/graph_fusion/{api,schemas,config}.py`
exactly. If the backend contract changes, update `src/lib/types.ts` and
`src/lib/config.ts` only; every component imports from there.

| Endpoint | Returns |
|---|---|
| `GET /health` | `{ status, region }` |
| `GET /model` | `ModelSnapshot`: Version A (simulated ocean) grid points |
| `GET /observations` | `ObservationSnapshot`: Version B (real sensor) points |
| `GET /fused?engine=auto\|gnn\|fallback` | `FusedResponse`: corrected points with `confidence`, `trust_label` (`green`/`amber`/`red`), `is_sensor_node`, plus a `FusionSummary` |
| `WS /alerts` | **Not yet exposed by the API.** Belongs to the Drift Memory Engine track. The Digital Twin page's alert panel says so honestly instead of showing a fabricated feed. |

Trust thresholds (from `config.py`, rendered as a legend on the Digital Twin
page): **green >= 70% confidence, amber >= 40%, red below 40%.** The frontend
never re-derives this client-side; it only ever displays the `trust_label`
the backend already computed.

Region scope lock: **Bay of Bengal**, `lat 5-22°N`, `lon 80-100°E`,
region key `bay_of_bengal`, see `src/lib/config.ts`.

---

## 5. What's real vs. what's a placeholder

Being explicit about this so nobody, teammate or judge, mistakes one for the
other:

- **Real and live:** everything on `/digital-twin` once the backend is
  running. `/health`, `/model`, `/observations`, `/fused` are genuinely
  fetched, and the trust colors/confidence numbers shown are the backend's
  actual GNN/fallback output, not sample data.
- **Real and static:** all copy on Home/Services/About is drawn directly from
  `../Problem_approach/SIH_67_APPROACH.pdf` and the work-distribution docs:
  the architecture layers, the competitive table, the "why now" citations,
  the delivery timeline, the PS metadata.
- **Honestly not built yet:** the live alert feed (`/alerts`, Drift Memory
  Engine track) and the full CesiumJS draped-ocean-surface 3D scene described
  in the approach doc's Visualization Layer. The Digital Twin page today
  renders fused points on the realistic `Globe` component plus a data table
  as an interim, real-data view. Swapping in the full CesiumJS scene (owned
  by Person 4 per the work-distribution doc) is the next build step, not a
  hidden gap.
- **Marked "Future Scope" on purpose:** the Nowcast Engine, per the team's own
  risk/fallback plan. It's presented as a roadmap item, never as a shipped
  feature.

---

## 6. Tech stack

- **React 19 + TypeScript + Vite** (scaffolded via `npm create vite@latest -- --template react-ts`)
- **Tailwind CSS v4** (CSS-first config via `@theme`/`@custom-variant` in `index.css`, `@tailwindcss/vite` plugin, no `tailwind.config.js` needed)
- **React Router** for the four pages, with `Services`/`About`/`DigitalTwin` code-split via `React.lazy`
- **GSAP + ScrollTrigger** for scroll reveals
- **Three.js + React Three Fiber + drei** for the realistic textured Earth (day/cloud/night-lights maps, Fresnel atmosphere shader, `OrbitControls`, `Stars`)
- **oxlint** for linting (already configured by the Vite scaffold)

No CesiumJS dependency yet. It's a heavier engine reserved for the real
draped-ocean-surface Digital Twin scene described in §5, to keep the current
build simpler while that's still ahead.

---

## 7. Known limitations / next steps

- Digital Twin's 3D view is the realistic `Globe` component, not the full
  CesiumJS draped-ocean-surface scene from the approach doc's Visualization
  Layer yet.
- No `/alerts` WebSocket wiring, waiting on the Drift Memory Engine track.
- No automated test suite yet (Vitest + React Testing Library would be the
  natural fit given the Vite setup, if time allows before the demo).
- Main JS bundle is ~1.3MB (~370KB gzip), mostly Three.js/R3F/drei, plus
  ~1.7MB of Earth texture JPGs loaded once by the globe. Acceptable for a
  hackathon demo; lazy-loading the `Globe` component behind a `Suspense`
  boundary is the obvious next lever if load time becomes a concern.
