import type { ReactElement } from "react";
import { Reveal } from "../components/Reveal";

type EngineStatus = "live" | "in-development" | "planned";

const STATUS_LABEL: Record<EngineStatus, string> = {
  live: "Live",
  "in-development": "In development",
  planned: "Planned",
};

function StatusBadge({ status }: { status: EngineStatus }) {
  const style =
    status === "live"
      ? { backgroundColor: "var(--color-accent)", color: "var(--color-bg)" }
      : status === "in-development"
        ? { border: "1px solid var(--color-accent)", color: "var(--color-accent)" }
        : { border: "1px solid var(--color-border)", color: "var(--color-ink-muted)" };

  return (
    <span className="font-nav inline-flex items-center rounded-full px-2.5 py-1 text-[10px]" style={style}>
      {STATUS_LABEL[status]}
    </span>
  );
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

function AlertWaveIcon() {
  return (
    <svg viewBox="0 0 32 32" width="26" height="26" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 20c2.5 0 2.5-3 5-3s2.5 3 5 3 2.5-3 5-3 2.5 3 5 3" />
      <path d="M16 5v9M16 18.5v.01" />
      <circle cx="16" cy="7" r="3.4" />
    </svg>
  );
}

function ClockForecastIcon() {
  return (
    <svg viewBox="0 0 32 32" width="26" height="26" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="15" cy="17" r="10.5" />
      <path d="M15 10.5V17l5 3" />
      <path d="M11 3.5h8" />
    </svg>
  );
}

function ModelWavesIcon() {
  return (
    <svg viewBox="0 0 32 32" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
      <path d="M4 11c3 0 3-4 6-4s3 4 6 4 3-4 6-4 3 4 6 4" />
      <path d="M4 18.5c3 0 3-4 6-4s3 4 6 4 3-4 6-4 3 4 6 4" />
      <path d="M4 26c3 0 3-4 6-4s3 4 6 4 3-4 6-4 3 4 6 4" />
    </svg>
  );
}

function BuoyIcon() {
  return (
    <svg viewBox="0 0 32 32" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M16 4v6M11 4h10" />
      <circle cx="16" cy="16" r="7" />
      <path d="M4 26c2.5-2.5 5.5-2.5 8-1s5.5 1.5 8 0 5.5-2.5 8 0" />
    </svg>
  );
}

const ENGINES: {
  slug: string;
  name: string;
  status: EngineStatus;
  owner: string;
  body: string;
  icon: () => ReactElement;
}[] = [
  {
    slug: "graph-fusion-engine",
    name: "Graph Fusion Engine",
    status: "live",
    owner: "36 automated tests passing",
    icon: GraphIcon,
    body: "Corrects the model grid using a graph of real sensor readings. Nodes are in-situ sensors, edges weighted by real oceanographic connectivity, current alignment, depth similarity, distance decay, not straight-line distance. Runs a PyTorch Geometric GNN with an automatic fallback to a simpler graph-weighted correction if training proves unstable.",
  },
  {
    slug: "drift-memory-engine",
    name: "Drift Memory Engine",
    status: "in-development",
    owner: "Team track",
    icon: AlertWaveIcon,
    body: "A rolling per-region \"surprise\" score that flags model-vs-reality divergence live, firing an alert when the divergence crosses a threshold, for example \"Drift detected: Bay of Bengal, SST diverging 1.8°C from forecast.\" Served over /alerts once complete.",
  },
  {
    slug: "nowcast-engine",
    name: "Nowcast Engine",
    status: "planned",
    owner: "Streaming Backbone track",
    icon: ClockForecastIcon,
    body: "A ConvLSTM-inspired short-range prediction layer, sitting on top of the streaming ingestion backbone. On the roadmap; not part of the current release.",
  },
];

const API_CONTRACT = [
  { method: "GET", path: "/health", body: "{ status, region }" },
  { method: "GET", path: "/model", body: "ModelSnapshot: region, time, resolution_deg, source, points[] (sst_c, current_u/v_ms, wave_height_m)" },
  { method: "GET", path: "/observations", body: "ObservationSnapshot: region, time, source, points[] (sensor_id, sensor_type, sst_c, current_u/v_ms, wave_height_m)" },
  { method: "GET", path: "/fused?engine=auto|gnn|fallback", body: "FusedResponse: points[] with correction_*, confidence, trust_label (green/amber/red), plus a FusionSummary" },
  { method: "WS", path: "/alerts", body: "Live push from the Drift Memory Engine. Not yet exposed by this API." },
];

const DATA_SOURCES = [
  {
    label: "Ocean model",
    tag: "Version A · simulated",
    icon: ModelWavesIcon,
    detail: "INCOIS LAS (primary), Copernicus Marine GLORYS reanalysis (fallback).",
    variables: ["Sea Surface Temperature", "Currents (u/v)", "Wave Height", "Salinity", "Chlorophyll"],
  },
  {
    label: "In-situ observations",
    tag: "Version B · measured",
    icon: BuoyIcon,
    detail: "Argo floats and gliders via Ifremer FTP, general in-situ via NOAA World Ocean Database.",
    variables: ["Moorings", "HF-radar", "ADCP (extensible adapter pattern)"],
  },
];

export function Services() {
  return (
    <div>
      <div className="px-6 py-28" style={{ backgroundColor: "var(--color-bg-raised)" }}>
        <div className="mx-auto max-w-5xl">
          <Reveal>
            <p className="font-nav text-xs opacity-60">How it works</p>
            <h1 className="font-display gradient-text mt-3 text-5xl sm:text-6xl">The engines behind VARUNA</h1>
            <p className="mt-6 max-w-2xl text-sm opacity-75 sm:text-base">
              Five layers, one non-negotiable floor: real model data, real in-situ data, and at
              least one visible fusion signal, correcting the forecast against what sensors are
              actually reading right now.
            </p>
          </Reveal>
        </div>
      </div>

      <div className="mx-auto max-w-5xl px-6 py-24">
        <div className="grid gap-6 sm:grid-cols-3">
          {ENGINES.map((engine) => (
            <Reveal key={engine.name} id={engine.slug} className="scroll-anchor h-full">
              <div
                className="flex h-full flex-col gap-4 rounded-2xl border p-6"
                style={{ borderColor: "var(--color-border)" }}
              >
                <div className="flex items-start justify-between">
                  <span style={{ color: "var(--color-accent)" }}>
                    <engine.icon />
                  </span>
                  <StatusBadge status={engine.status} />
                </div>
                <div>
                  <h2 className="font-nav text-sm">{engine.name}</h2>
                  <p className="mt-1 text-xs opacity-50">{engine.owner}</p>
                </div>
                <p className="text-sm opacity-75">{engine.body}</p>
              </div>
            </Reveal>
          ))}
        </div>

        <Reveal id="data-layer" className="scroll-anchor mt-24">
          <h2 className="font-display text-3xl">Data layer</h2>
          <div className="mt-8 grid gap-6 sm:grid-cols-2">
            {DATA_SOURCES.map((source) => (
              <div key={source.label} className="rounded-2xl border p-6" style={{ borderColor: "var(--color-border)" }}>
                <div className="flex items-center gap-3" style={{ color: "var(--color-accent)" }}>
                  <source.icon />
                  <h3 className="font-nav text-sm" style={{ color: "var(--color-ink)" }}>{source.label}</h3>
                </div>
                <p className="font-mono-data mt-3 text-xs opacity-50">{source.tag}</p>
                <p className="mt-3 text-sm opacity-75">{source.detail}</p>
                <div className="mt-4 flex flex-wrap gap-2">
                  {source.variables.map((v) => (
                    <span
                      key={v}
                      className="font-nav rounded-full px-2.5 py-1 text-[10px] opacity-70"
                      style={{ border: "1px solid var(--color-border)" }}
                    >
                      {v}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Reveal>

        <Reveal id="api-contract" className="scroll-anchor mt-24">
          <h2 className="font-display text-3xl">API contract</h2>
          <p className="mt-3 text-sm opacity-60">
            FastAPI + WebSocket, served at <code className="font-mono-data">localhost:8000</code>{" "}
            in development. This is the real, current contract from{" "}
            <code className="font-mono-data">varuna-graph-fusion/src/graph_fusion</code>.
          </p>
          <div className="mt-8 divide-y" style={{ borderColor: "var(--color-border)" }}>
            {API_CONTRACT.map((route) => (
              <div key={route.path} className="flex flex-col gap-2 py-4 sm:flex-row sm:items-baseline sm:gap-4" style={{ borderColor: "var(--color-border)" }}>
                <span
                  className="font-nav w-14 shrink-0 rounded-full px-2.5 py-1 text-center text-[10px]"
                  style={
                    route.method === "WS"
                      ? { border: "1px solid var(--color-accent)", color: "var(--color-accent)" }
                      : { backgroundColor: "var(--color-accent)", color: "var(--color-bg)" }
                  }
                >
                  {route.method}
                </span>
                <p className="font-mono-data w-56 shrink-0 text-sm" style={{ color: "var(--color-accent)" }}>{route.path}</p>
                <p className="text-sm opacity-70">{route.body}</p>
              </div>
            ))}
          </div>
        </Reveal>
      </div>
    </div>
  );
}
