import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { Globe } from "../components/globe/Globe";
import { CoordinateReadout } from "../components/CoordinateReadout";
import { Reveal } from "../components/Reveal";
import { useI18n } from "../i18n/I18nProvider";
import { useTheme } from "../theme/ThemeProvider";
import { useInView } from "../lib/useInView";
import { REGION_BBOX, REGION_CENTER, REGION_LABEL } from "../lib/config";
import SplashCursor from "../components/effects/SplashCursor";
import RippleDistortion from "../components/effects/RippleDistortion";
import oceanWaves from "../assets/effects/ocean-waves.jpg";

function LiveStatusCard() {
  const [status, setStatus] = useState<"checking" | "online" | "offline">("checking");

  useEffect(() => {
    let cancelled = false;
    api
      .health()
      .then(() => !cancelled && setStatus("online"))
      .catch(() => !cancelled && setStatus("offline"));
    return () => {
      cancelled = true;
    };
  }, []);

  const dotColor = status === "online" ? "var(--color-trust-green)" : status === "offline" ? "var(--color-trust-red)" : "var(--color-ink-muted)";

  return (
    <div className="rounded-2xl border p-6" style={{ borderColor: "var(--color-border)" }}>
      <div className="flex items-center gap-2">
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-60" style={{ backgroundColor: dotColor }} />
          <span className="relative inline-flex h-2 w-2 rounded-full" style={{ backgroundColor: dotColor }} />
        </span>
        <h3 className="font-nav text-xs opacity-70">Live status</h3>
      </div>
      <p className="mt-4 text-sm opacity-80">
        {status === "checking" && "Checking the Graph Fusion Engine..."}
        {status === "online" && "Backend online. Real model and sensor data are flowing."}
        {status === "offline" && "Backend offline right now. Run it locally to see live data."}
      </p>
      <p className="mt-3 text-xs opacity-50">
        Drift alerts aren't wired in yet, the Drift Memory Engine's /alerts endpoint isn't built.
        This card shows what's actually connected, not a placeholder feed.
      </p>
    </div>
  );
}

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const onChange = () => setReduced(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return reduced;
}

function GraphIcon() {
  return (
    <svg viewBox="0 0 32 32" width="26" height="26" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
      <circle cx="7" cy="9" r="3" />
      <circle cx="25" cy="7" r="3" />
      <circle cx="9" cy="24" r="3" />
      <circle cx="24" cy="22" r="3" />
      <path d="M9.6 7.3 22.4 7.7M8 12v9M11.5 22 21.5 9.5M22 10l1.7 9" />
    </svg>
  );
}

function BellWaveIcon() {
  return (
    <svg viewBox="0 0 32 32" width="26" height="26" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 20c2.5 0 2.5-3 5-3s2.5 3 5 3 2.5-3 5-3 2.5 3 5 3" />
      <path d="M16 5v9M16 18.5v.01" />
      <circle cx="16" cy="7" r="3.4" />
    </svg>
  );
}

function GlobeIcon() {
  return (
    <svg viewBox="0 0 32 32" width="26" height="26" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
      <circle cx="16" cy="16" r="12" />
      <path d="M4 16h24M16 4c3.3 3.5 5 8 5 12s-1.7 8.5-5 12c-3.3-3.5-5-8-5-12s1.7-8.5 5-12Z" />
    </svg>
  );
}

function ToggleIcon() {
  return (
    <svg viewBox="0 0 32 32" width="26" height="26" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
      <rect x="4" y="11" width="24" height="10" rx="5" />
      <circle cx="21" cy="16" r="3.4" fill="currentColor" stroke="none" />
    </svg>
  );
}

const DIFFERENTIATORS = [
  {
    icon: GraphIcon,
    title: "Graph-based fusion, not distance interpolation",
    body: "Sensors become nodes in a graph, edges weighted by real oceanographic connectivity, current alignment, depth similarity, decay with distance, so the correction respects how water actually moves.",
  },
  {
    icon: BellWaveIcon,
    title: "Live drift alerts, not manual validation",
    body: "A rolling per-region divergence score watches the gap between model and reality continuously, instead of a scientist comparing snapshots by hand once in a while.",
  },
  {
    icon: GlobeIcon,
    title: "A real 3D digital twin, not 2D map overlays",
    body: "INCOIS's own Ocean State Forecast is 2D GIS overlays today. This is a fully interactive, photographically-textured 3D globe you can rotate and inspect.",
  },
  {
    icon: ToggleIcon,
    title: "One tool, two audiences",
    body: "A researcher reading raw confidence stats and a fisherman reading a simple safe / caution / avoid signal are looking at the same fused data, through different lenses.",
  },
];

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
    detail: "REST + WebSocket: /model /observations /fused /alerts (live push)",
  },
  {
    name: "3D Visualization",
    detail: "CesiumJS / Three.js: draped ocean surfaces, animated current vectors, time-scrubber, click-to-inspect, live alert feed",
  },
];

const WHY_NOW = [
  {
    title: "A global movement, not a hackathon concept",
    body: "The EU's EDITO platform (Horizon Europe, 2022-2028) and the UN Decade of Ocean Science's DITTO initiative are actively building Digital Twin of the Ocean tooling. The next DITTO Summit runs November 2026 in Yokohama.",
  },
  {
    title: "MoES is already asking for exactly this",
    body: "MoES convened a panel, “AI for Our Oceans of Tomorrow: Data, Models and Governance,” at the India AI Impact Summit 2026, calling for integrating AI-enabled models with traditional physical ocean models.",
  },
  {
    title: "Real government money is moving here",
    body: "India's Deep Ocean Mission (~₹4,077 crore over 5 years) and the Blue Economy (a $1 trillion+ opportunity) are funded, active priorities, and INCOIS already runs an in-house AI/ML El Niño prediction system.",
  },
];

const BUILD_STATUS = [
  { name: "Graph Fusion Engine", status: "Live", detail: "36 automated tests passing, GNN with automatic fallback" },
  { name: "Drift Memory Engine", status: "In development", detail: "Rolling per-region surprise score, feeds /alerts" },
  { name: "Nowcast Engine", status: "Planned", detail: "ConvLSTM-inspired short-range prediction" },
  { name: "This site", status: "Live", detail: "Realistic 3D globe, dual-mode Digital Twin, multilingual" },
];

const RESEARCH_REFERENCES = [
  { name: "Graph Neural Networks", body: "Graph-structured reasoning over the sensor network. Powers the Graph Fusion Engine." },
  { name: "Titans (test-time memory)", body: "Neural memory that updates itself at inference. Inspiration for the Drift Memory Engine's surprise score." },
  { name: "Mamba / State Space Models", body: "Linear-time sequence recurrence. Inspiration for the streaming ingestion backbone." },
  { name: "V-JEPA2", body: "Predicts future states in a compressed latent space. Inspiration for the Nowcast Engine (stretch goal)." },
];

const COMPETITIVE_TABLE = [
  { tool: "INCOIS OSF (current, deployed)", threeD: "No, 2D GIS overlays", fusion: "No", india: "Yes", dualMode: "No" },
  { tool: "EU EDITO / Digital Twin Ocean", threeD: "Partial, data/model access", fusion: "Emerging", india: "No, Europe-focused", dualMode: "No, expert-oriented" },
  { tool: "Academic tools (pyParaOcean, GODIVA)", threeD: "Yes", fusion: "No", india: "No", dualMode: "No, never deployed" },
  { tool: "VARUNA (ours)", threeD: "Yes", fusion: "Yes", india: "Yes", dualMode: "Yes" },
];

export function Home() {
  const [center, setCenter] = useState(REGION_CENTER);
  const { t } = useI18n();
  const { theme } = useTheme();
  const reduceMotion = usePrefersReducedMotion();
  const [updatesTab, setUpdatesTab] = useState<"status" | "research">("status");
  const [heroRef, heroInView] = useInView<HTMLElement>({ threshold: 0.15 });
  const [rippleRef, rippleInView] = useInView<HTMLElement>({ once: true });

  return (
    <>
      <section ref={heroRef} className="relative flex min-h-screen items-center overflow-hidden pt-32">
        <div className="gradient-wash pointer-events-none absolute inset-0 opacity-60" />
        {!reduceMotion && heroInView && (
          <div className="pointer-events-none absolute inset-0" style={{ opacity: 0.35 }}>
            <SplashCursor
              RAINBOW_MODE={false}
              COLOR="#0b345a"
              SHADING={false}
              SIM_RESOLUTION={32}
              DYE_RESOLUTION={400}
              DENSITY_DISSIPATION={6}
              VELOCITY_DISSIPATION={3}
              SPLAT_RADIUS={0.12}
              SPLAT_FORCE={2500}
              CURL={2}
              PRESSURE_ITERATIONS={6}
            />
          </div>
        )}
        <div className="relative z-10 mx-auto grid w-full max-w-7xl grid-cols-1 items-center gap-12 px-6 lg:grid-cols-[1.1fr_1fr]">
          <div>
            <p className="font-nav text-xs opacity-60">{t("hero.eyebrow")}</p>
            <h1 className="font-display gradient-text mt-4 text-6xl leading-[0.95] sm:text-7xl lg:text-8xl">
              {t("hero.headline1")}
              <br />
              {t("hero.headline2")}
              <br />
              {t("hero.headline3")}
            </h1>
            <p className="mt-6 max-w-lg text-lg opacity-80">{t("hero.pitch")}</p>
            <div className="mt-8 flex flex-wrap gap-4">
              <Link
                to="/digital-twin"
                className="font-nav rounded-full px-6 py-3 text-xs"
                style={{ backgroundColor: "var(--color-accent)", color: "var(--color-bg)" }}
              >
                {t("hero.ctaPrimary")}
              </Link>
              <Link to="/services" className="font-nav rounded-full border px-6 py-3 text-xs" style={{ borderColor: "var(--color-border)" }}>
                {t("hero.ctaSecondary")}
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

      <section id="the-gap" className="scroll-anchor mx-auto max-w-5xl px-6 py-28">
        <Reveal>
          <p className="font-nav text-xs opacity-60">The problem, explained properly</p>
          <h2 className="font-display mt-3 text-4xl sm:text-5xl">Two oceans that don't talk to each other</h2>
        </Reveal>

        <div className="mt-14 grid gap-10 sm:grid-cols-2">
          <Reveal>
            <h3 className="font-nav text-xs opacity-60">Version A: the simulated ocean</h3>
            <p className="mt-3">
              INCOIS runs the Indian Ocean Forecast System on ROMS/HYCOM models: a dense 3D+time
              grid of currents, waves, sea surface temperature and mixed layer depth, forecasting
              5-10 days ahead. A simulation: physics equations solved on a grid, not a direct
              measurement.
            </p>
          </Reveal>
          <Reveal>
            <h3 className="font-nav text-xs opacity-60">Version B: the real ocean</h3>
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
              Validating the simulation against reality today is a manual, periodic process:
              scientists compare snapshots in desktop tools like MATLAB, ParaView and Panoply.
              There is no single interactive, browser-based, 3D space where both versions of the
              ocean sit together, continuously, for anyone (researcher, naval officer, or
              fisherman) to explore and trust.
            </p>
          </div>
        </Reveal>
      </section>

      <section id="what-makes-it-different" className="scroll-anchor mx-auto max-w-5xl px-6 py-28">
        <Reveal>
          <p className="font-nav text-xs opacity-60">What makes it different</p>
          <h2 className="font-display mt-3 text-4xl sm:text-5xl">Not just another dashboard</h2>
        </Reveal>
        <div className="mt-14 grid gap-8 sm:grid-cols-2">
          {DIFFERENTIATORS.map((item) => (
            <Reveal key={item.title} className="flex gap-4">
              <span className="shrink-0" style={{ color: "var(--color-accent)" }}>
                <item.icon />
              </span>
              <div>
                <h3 className="font-nav text-sm">{item.title}</h3>
                <p className="mt-2 text-sm opacity-75">{item.body}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      <section id="architecture" className="scroll-anchor px-6 py-28" style={{ backgroundColor: "var(--color-bg-raised)" }}>
        <div className="mx-auto max-w-5xl">
          <Reveal>
            <p className="font-nav text-xs opacity-60">System architecture</p>
            <h2 className="font-display mt-3 text-4xl sm:text-5xl">Fuse → Detect → Validate → Serve → Show</h2>
          </Reveal>

          <div className="mt-14 space-y-4">
            {ARCHITECTURE_LAYERS.map((layer, i) => (
              <Reveal key={layer.name}>
                <div className="flex flex-col gap-1 border-b pb-4 sm:flex-row sm:items-baseline sm:gap-6" style={{ borderColor: "var(--color-border)" }}>
                  <span className="font-display w-10 shrink-0 text-2xl opacity-40">
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

      <section id="why-now" className="scroll-anchor mx-auto max-w-5xl px-6 py-28">
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

      <section id="build-status" className="scroll-anchor mx-auto max-w-5xl px-6 py-28">
        <Reveal>
          <p className="font-nav text-xs opacity-60">Where things stand</p>
          <h2 className="font-display mt-3 text-4xl sm:text-5xl">Build status, honestly</h2>
        </Reveal>

        <div className="mt-12 grid gap-8 lg:grid-cols-[1.4fr_1fr]">
          <Reveal className="rounded-2xl border p-6" >
            <div style={{ borderColor: "var(--color-border)" }}>
              <div className="flex gap-6 border-b pb-3" style={{ borderColor: "var(--color-border)" }}>
                <button
                  type="button"
                  onClick={() => setUpdatesTab("status")}
                  className="font-nav text-xs"
                  style={{ opacity: updatesTab === "status" ? 1 : 0.5 }}
                >
                  Build status
                </button>
                <button
                  type="button"
                  onClick={() => setUpdatesTab("research")}
                  className="font-nav text-xs"
                  style={{ opacity: updatesTab === "research" ? 1 : 0.5 }}
                >
                  Research references
                </button>
              </div>

              {updatesTab === "status" && (
                <ul className="mt-4 space-y-3">
                  {BUILD_STATUS.map((row) => (
                    <li key={row.name} className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:gap-4">
                      <span className="font-nav w-44 shrink-0 text-xs">{row.name}</span>
                      <span
                        className="font-mono-data w-28 shrink-0 text-xs"
                        style={{ color: row.status === "Live" ? "var(--color-trust-green)" : "var(--color-ink-muted)" }}
                      >
                        {row.status}
                      </span>
                      <span className="text-xs opacity-70">{row.detail}</span>
                    </li>
                  ))}
                </ul>
              )}

              {updatesTab === "research" && (
                <ul className="mt-4 space-y-3">
                  {RESEARCH_REFERENCES.map((row) => (
                    <li key={row.name}>
                      <span className="font-nav text-xs">{row.name}</span>
                      <span className="ml-2 text-xs opacity-70">{row.body}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </Reveal>

          <Reveal>
            <LiveStatusCard />
          </Reveal>
        </div>
      </section>

      <section id="competitive-landscape" className="scroll-anchor px-6 py-28" style={{ backgroundColor: "var(--color-bg-raised)" }}>
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

      <section
        ref={rippleRef}
        className="relative h-[60vh] min-h-[420px] overflow-hidden"
        style={{ backgroundColor: "var(--palette-celestial-canvas, #091e39)" }}
      >
        {rippleInView && (
          <RippleDistortion
            src={oceanWaves}
            className="absolute inset-0"
            grayscale
            tint={theme === "dark" ? "#79a4c0" : "#0b345a"}
            tintAmount={0.45}
            strength={0.16}
            swirl={0.6}
            rings={3}
            spread={4}
            fade={2.5}
            spacing={12}
            trigger="hover"
            quality="low"
          />
        )}
        <div
          className="pointer-events-none absolute inset-0"
          style={{ background: "linear-gradient(rgba(0,0,0,0.15), rgba(0,0,0,0.45))" }}
        />
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center px-6 text-center text-white">
          <p className="font-nav text-xs opacity-80">The Bay of Bengal</p>
          <h2 className="font-display mt-3 text-4xl sm:text-5xl">Touch the surface</h2>
          <p className="mt-3 max-w-md text-sm opacity-90">
            Hover to disturb the water. Everywhere on this site, VARUNA is watching the same
            restless ocean.
          </p>
        </div>
        <p className="pointer-events-none absolute bottom-3 right-4 text-[10px] text-white opacity-60">
          Photo: Ksheera Piraati, CC BY 4.0
        </p>
      </section>

      <section className="mx-auto max-w-5xl px-6 py-32 text-center">
        <Reveal>
          <h2 className="font-display text-4xl sm:text-5xl">See the fusion engine live</h2>
          <p className="mx-auto mt-4 max-w-xl opacity-70">
            The Graph Fusion Engine is built and tested. Connect it below to watch real model
            output get corrected against real sensor readings, point by point.
          </p>
          <Link
            to="/digital-twin"
            className="font-nav mt-8 inline-block rounded-full px-8 py-4 text-xs"
            style={{ backgroundColor: "var(--color-accent)", color: "var(--color-bg)" }}
          >
            {t("hero.ctaPrimary")}
          </Link>
        </Reveal>
      </section>
    </>
  );
}
