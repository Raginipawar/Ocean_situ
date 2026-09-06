import { useState } from "react";
import { Link } from "react-router-dom";
import { Globe } from "../components/globe/Globe";
import { CoordinateReadout } from "../components/CoordinateReadout";
import { Reveal } from "../components/Reveal";
import { REGION_BBOX, REGION_CENTER, REGION_LABEL } from "../lib/config";

const ARCHITECTURE_LAYERS = [
  {
    name: "Data Sources",
    detail: "ROMS/HYCOM reanalysis (NetCDF, gridded model output) · Argo floats, moored buoys, XBT, drifters (real point data)",
  },
  {
    name: "Ingestion & Processing",
    detail: "xarray / netCDF4 parsers → regrid to common resolution → chunk into lightweight JSON tiles (FastAPI)",
  },
  {
    name: "Intelligence Layer",
    detail: "Graph Fusion Engine corrects the model grid using real sensor readings · Drift Memory Engine flags model-vs-reality divergence live · Nowcast Engine (stretch goal)",
  },
  {
    name: "API Layer",
    detail: "REST + WebSocket — /model /observations /fused /alerts (live push)",
  },
  {
    name: "3D Visualization",
    detail: "CesiumJS / Three.js — draped ocean surfaces, animated current vectors, time-scrubber, click-to-inspect, live alert feed",
  },
];

const WHY_NOW = [
  {
    title: "A global movement, not a hackathon concept",
    body: "The EU's EDITO platform (Horizon Europe, 2022–2028) and the UN Decade of Ocean Science's DITTO initiative are actively building Digital Twin of the Ocean tooling — the next DITTO Summit runs November 2026 in Yokohama.",
  },
  {
    title: "MoES is already asking for exactly this",
    body: "MoES convened a panel, “AI for Our Oceans of Tomorrow: Data, Models and Governance,” at the India AI Impact Summit 2026, calling for integrating AI-enabled models with traditional physical ocean models.",
  },
  {
    title: "Real government money is moving here",
    body: "India's Deep Ocean Mission (~₹4,077 crore over 5 years) and the Blue Economy (a $1 trillion+ opportunity) are funded, active priorities — and INCOIS already runs an in-house AI/ML El Niño prediction system.",
  },
];

const COMPETITIVE_TABLE = [
  { tool: "INCOIS OSF (current, deployed)", threeD: "No — 2D GIS overlays", fusion: "No", india: "Yes", dualMode: "No" },
  { tool: "EU EDITO / Digital Twin Ocean", threeD: "Partial — data/model access", fusion: "Emerging", india: "No — Europe-focused", dualMode: "No — expert-oriented" },
  { tool: "Academic tools (pyParaOcean, GODIVA)", threeD: "Yes", fusion: "No", india: "No", dualMode: "No — never deployed" },
  { tool: "VARUNA (ours)", threeD: "Yes", fusion: "Yes", india: "Yes", dualMode: "Yes" },
];

export function Home() {
  const [center, setCenter] = useState(REGION_CENTER);

  return (
    <>
      <section className="relative flex min-h-screen items-center overflow-hidden pt-24">
        <div className="gradient-wash pointer-events-none absolute inset-0 opacity-60" />
        <div className="relative mx-auto grid w-full max-w-7xl grid-cols-1 items-center gap-12 px-6 lg:grid-cols-[1.1fr_1fr]">
          <div>
            <p className="font-nav text-xs opacity-60">SIH26067 · Ministry of Earth Sciences · Disaster Management</p>
            <h1 className="font-display mt-4 text-6xl leading-[0.95] sm:text-7xl lg:text-8xl">
              A living
              <br />
              digital twin
              <br />
              of the ocean
            </h1>
            <p className="mt-6 max-w-lg text-lg italic opacity-80">
              VARUNA fuses INCOIS forecast data with real Argo, glider, CTD and buoy readings —
              and actively flags where the model and reality disagree, instead of leaving that
              comparison to manual, periodic desktop work.
            </p>
            <div className="mt-8 flex flex-wrap gap-4">
              <Link
                to="/digital-twin"
                className="font-nav rounded-full px-6 py-3 text-xs"
                style={{ backgroundColor: "var(--color-ink)", color: "var(--color-bg)" }}
              >
                Open the Digital Twin
              </Link>
              <Link to="/services" className="font-nav rounded-full border px-6 py-3 text-xs" style={{ borderColor: "var(--color-border)" }}>
                How it works
              </Link>
            </div>
          </div>

          <div className="flex flex-col items-center gap-4">
            <Globe
              focus={REGION_CENTER}
              regionBBox={REGION_BBOX}
              onCenterChange={setCenter}
              className="w-full max-w-[560px]"
            />
            <CoordinateReadout label={REGION_LABEL} lat={center.lat} lon={center.lon} className="opacity-70" />
            <p className="max-w-xs text-center text-xs opacity-50">
              Drag to rotate. Highlighted region is VARUNA's scope-locked demo area.
            </p>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-6 py-28">
        <Reveal>
          <p className="font-nav text-xs opacity-60">The problem, explained properly</p>
          <h2 className="font-display mt-3 text-4xl sm:text-5xl">Two oceans that don't talk to each other</h2>
        </Reveal>

        <div className="mt-14 grid gap-10 sm:grid-cols-2">
          <Reveal>
            <h3 className="font-nav text-xs opacity-60">Version A — the simulated ocean</h3>
            <p className="mt-3">
              INCOIS runs the Indian Ocean Forecast System on ROMS/HYCOM models — a dense 3D+time
              grid of currents, waves, sea surface temperature and mixed layer depth, forecasting
              5–10 days ahead. A simulation: physics equations solved on a grid, not a direct
              measurement.
            </p>
          </Reveal>
          <Reveal>
            <h3 className="font-nav text-xs opacity-60">Version B — the real ocean</h3>
            <p className="mt-3">
              Argo floats, moored buoys, XBT casts and drifters physically measure temperature,
              salinity and currents at scattered points. Sparse in space, irregular in time, but
              ground truth.
            </p>
          </Reveal>
        </div>

        <Reveal className="mt-14 rounded-2xl border p-8" >
          <div style={{ borderColor: "var(--color-border)" }}>
            <h3 className="font-nav text-xs opacity-60">The actual gap</h3>
            <p className="mt-3">
              Validating the simulation against reality today is a manual, periodic process —
              scientists compare snapshots in desktop tools like MATLAB, ParaView and Panoply.
              There is no single interactive, browser-based, 3D space where both versions of the
              ocean sit together, continuously, for anyone — researcher, naval officer, or
              fisherman — to explore and trust.
            </p>
          </div>
        </Reveal>
      </section>

      <section className="px-6 py-28" style={{ backgroundColor: "var(--color-bg-raised)" }}>
        <div className="mx-auto max-w-5xl">
          <Reveal>
            <p className="font-nav text-xs opacity-60">System architecture</p>
            <h2 className="font-display mt-3 text-4xl sm:text-5xl">Fuse → Detect → Validate → Serve → Show</h2>
          </Reveal>

          <div className="mt-14 space-y-4">
            {ARCHITECTURE_LAYERS.map((layer, i) => (
              <Reveal key={layer.name}>
                <div className="flex flex-col gap-1 border-b pb-4 sm:flex-row sm:items-baseline sm:gap-6" style={{ borderColor: "var(--color-border)" }}>
                  <span className="font-mono-data w-10 shrink-0 text-sm opacity-40">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <h3 className="font-nav w-56 shrink-0 text-sm">{layer.name}</h3>
                  <p className="text-sm opacity-75">{layer.detail}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-6 py-28">
        <Reveal>
          <p className="font-nav text-xs opacity-60">Why now</p>
          <h2 className="font-display mt-3 text-4xl sm:text-5xl">Where global ocean policy is heading</h2>
        </Reveal>

        <div className="mt-14 grid gap-10 sm:grid-cols-3">
          {WHY_NOW.map((item) => (
            <Reveal key={item.title}>
              <h3 className="font-nav text-sm">{item.title}</h3>
              <p className="mt-3 text-sm opacity-75">{item.body}</p>
            </Reveal>
          ))}
        </div>
      </section>

      <section className="px-6 py-28" style={{ backgroundColor: "var(--color-bg-raised)" }}>
        <div className="mx-auto max-w-5xl">
          <Reveal>
            <p className="font-nav text-xs opacity-60">Competitive landscape</p>
            <h2 className="font-display mt-3 text-4xl sm:text-5xl">Where VARUNA actually sits</h2>
          </Reveal>

          <Reveal className="mt-12 overflow-x-auto">
            <table className="w-full min-w-[640px] border-collapse text-sm">
              <thead>
                <tr className="font-nav text-left text-xs opacity-60" style={{ borderBottom: "1px solid var(--color-border)" }}>
                  <th className="py-3 pr-4">Tool</th>
                  <th className="py-3 pr-4">3D?</th>
                  <th className="py-3 pr-4">Live model↔observation fusion?</th>
                  <th className="py-3 pr-4">India/INCOIS-specific?</th>
                  <th className="py-3">Dual expert/public mode?</th>
                </tr>
              </thead>
              <tbody>
                {COMPETITIVE_TABLE.map((row) => (
                  <tr
                    key={row.tool}
                    style={{ borderBottom: "1px solid var(--color-border)" }}
                    className={row.tool.startsWith("VARUNA") ? "font-semibold" : ""}
                  >
                    <td className="py-3 pr-4">{row.tool}</td>
                    <td className="py-3 pr-4 opacity-80">{row.threeD}</td>
                    <td className="py-3 pr-4 opacity-80">{row.fusion}</td>
                    <td className="py-3 pr-4 opacity-80">{row.india}</td>
                    <td className="py-3 opacity-80">{row.dualMode}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Reveal>
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-6 py-32 text-center">
        <Reveal>
          <h2 className="font-display text-4xl sm:text-5xl">See the fusion engine live</h2>
          <p className="mx-auto mt-4 max-w-xl opacity-70">
            The Graph Fusion Engine is built and tested — connect it below to watch real model
            output get corrected against real sensor readings, point by point.
          </p>
          <Link
            to="/digital-twin"
            className="font-nav mt-8 inline-block rounded-full px-8 py-4 text-xs"
            style={{ backgroundColor: "var(--color-ink)", color: "var(--color-bg)" }}
          >
            Open the Digital Twin
          </Link>
        </Reveal>
      </section>
    </>
  );
}
