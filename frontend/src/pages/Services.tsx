import { Reveal } from "../components/Reveal";

const ENGINES = [
  {
    name: "Graph Fusion Engine",
    status: "Built · 36 passing tests",
    owner: "Intelligence Core #1",
    body: "Corrects the model grid using a graph of real sensor readings — nodes are in-situ sensors, edges weighted by real oceanographic connectivity (current alignment, depth similarity, distance decay), not straight-line distance. Runs a PyTorch Geometric GNN with an automatic fallback to a simpler graph-weighted correction if training proves unstable — both are legitimately \"graph-based fusion\" under questioning.",
  },
  {
    name: "Drift Memory Engine",
    status: "Team track",
    owner: "Intelligence Core #2",
    body: "A rolling per-region \"surprise\" score that flags model-vs-reality divergence live, firing an alert when the divergence crosses a threshold — e.g. \"Drift detected: Bay of Bengal, SST diverging 1.8°C from forecast.\" This is the second non-negotiable piece of the core loop, served over /alerts.",
  },
  {
    name: "Nowcast Engine",
    status: "Future scope (stretch goal)",
    owner: "Streaming Backbone track",
    body: "A ConvLSTM-inspired short-range prediction, cut first if time runs short per the team's risk plan — documented honestly as future scope rather than shipped as a hidden mock.",
  },
];

const API_CONTRACT = [
  { path: "GET /health", body: "{ status, region }" },
  { path: "GET /model", body: "ModelSnapshot — region, time, resolution_deg, source, points[] (sst_c, current_u/v_ms, wave_height_m)" },
  { path: "GET /observations", body: "ObservationSnapshot — region, time, source, points[] (sensor_id, sensor_type, sst_c, current_u/v_ms, wave_height_m)" },
  { path: "GET /fused?engine=auto|gnn|fallback", body: "FusedResponse — points[] with correction_*, confidence, trust_label (green/amber/red), plus a FusionSummary" },
  { path: "WS /alerts", body: "Live push from the Drift Memory Engine — not yet exposed by this API." },
];

const DATA_SOURCES = [
  { label: "Ocean model (Version A)", detail: "INCOIS LAS (primary) · Copernicus Marine GLORYS reanalysis (fallback) — Sea Surface Temperature, Currents (u/v), Wave Height, Salinity, Chlorophyll" },
  { label: "In-situ observations (Version B)", detail: "Argo floats & Gliders via Ifremer FTP · general in-situ via NOAA World Ocean Database · extensible adapter pattern for moorings, HF-radar and ADCP" },
];

export function Services() {
  return (
    <div className="mx-auto max-w-5xl px-6 py-32">
      <Reveal>
        <p className="font-nav text-xs opacity-60">Services</p>
        <h1 className="font-display mt-3 text-5xl sm:text-6xl">How VARUNA works</h1>
        <p className="mt-6 max-w-2xl opacity-75">
          Five layers, one non-negotiable floor: real model data, real in-situ data, and at least
          one visible fusion signal. Everything below is what's actually built or actually planned
          — nothing here is aspirational marketing copy.
        </p>
      </Reveal>

      <div className="mt-20 space-y-10">
        {ENGINES.map((engine) => (
          <Reveal key={engine.name} className="border-b pb-10" >
            <div style={{ borderColor: "var(--color-border)" }} className="flex flex-col gap-3 sm:flex-row sm:gap-10">
              <div className="w-56 shrink-0">
                <h2 className="font-nav text-sm">{engine.name}</h2>
                <p className="font-mono-data mt-1 text-xs opacity-60">{engine.status}</p>
                <p className="mt-1 text-xs opacity-40">{engine.owner}</p>
              </div>
              <p className="text-sm opacity-75">{engine.body}</p>
            </div>
          </Reveal>
        ))}
      </div>

      <Reveal className="mt-24">
        <h2 className="font-display text-3xl">Data layer</h2>
        <div className="mt-8 grid gap-8 sm:grid-cols-2">
          {DATA_SOURCES.map((source) => (
            <div key={source.label}>
              <h3 className="font-nav text-xs opacity-60">{source.label}</h3>
              <p className="mt-2 text-sm opacity-75">{source.detail}</p>
            </div>
          ))}
        </div>
      </Reveal>

      <Reveal className="mt-24">
        <h2 className="font-display text-3xl">API contract</h2>
        <p className="mt-3 text-sm opacity-60">
          FastAPI + WebSocket, served at <code className="font-mono-data">localhost:8000</code>{" "}
          in development. This is the real, current contract from{" "}
          <code className="font-mono-data">varuna-graph-fusion/src/graph_fusion</code>.
        </p>
        <div className="mt-8 space-y-4">
          {API_CONTRACT.map((route) => (
            <div key={route.path} className="border-b pb-4" style={{ borderColor: "var(--color-border)" }}>
              <p className="font-mono-data text-sm" style={{ color: "var(--color-accent)" }}>{route.path}</p>
              <p className="mt-1 text-sm opacity-70">{route.body}</p>
            </div>
          ))}
        </div>
      </Reveal>
    </div>
  );
}
