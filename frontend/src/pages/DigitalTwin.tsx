import { useCallback, useEffect, useMemo, useState } from "react";
import { Globe, type GlobeMarker } from "../components/globe/Globe";
import { AnnotationLayer } from "../components/Annotation";
import { CoordinateReadout } from "../components/CoordinateReadout";
import { PointInspector } from "../components/PointInspector";
import { TrustBadge } from "../components/TrustBadge";
import { api, driftApi, ApiError } from "../lib/api";
import {
  API_BASE_URL,
  DRIFT_API_BASE_URL,
  REGION_BBOX,
  REGION_CENTER,
  REGION_LABEL,
  TRUST_AMBER_MIN,
  TRUST_GREEN_MIN,
} from "../lib/config";
import type { Alert, FusedPoint, FusedResponse, TrustLabel } from "../lib/types";

/** Stable id for a fused point, shared between the globe markers, the
 * sensor list, and the click-to-inspect panel so all three can refer to
 * "the same point" without the backend needing to hand out real ids. */
const pointId = (p: { lat: number; lon: number }) => `${p.lat}-${p.lon}`;

const NEARBY_WINDOW_DEG = 3;
const NEARBY_MAX_POINTS = 80;

type ConnectionState = "checking" | "online" | "offline";
type Mode = "expert" | "public";

const TRUST_COLOR: Record<TrustLabel, string> = {
  green: "var(--color-trust-green)",
  amber: "var(--color-trust-amber)",
  red: "var(--color-trust-red)",
};

/**
 * The point in `points` nearest to `at` (plain lat/lon distance -- this is a
 * UI "what am I looking at" lookup over a regional-scale grid, not a
 * navigation calculation, so it doesn't need haversine precision).
 *
 * Deliberately NOT a global worst-case across the whole fused grid: a
 * fisherman near a well-covered green area shouldn't be told "Avoid"
 * because some unrelated corner of the Bay of Bengal disagrees. Public mode
 * answers "is it safe *here*," not "is it safe *anywhere in the region*."
 */
function nearestPoint(
  points: FusedResponse["points"],
  at: { lat: number; lon: number },
): FusedResponse["points"][number] | null {
  let best: FusedResponse["points"][number] | null = null;
  let bestDist = Infinity;
  for (const p of points) {
    const d = (p.lat - at.lat) ** 2 + (p.lon - at.lon) ** 2;
    if (d < bestDist) {
      bestDist = d;
      best = p;
    }
  }
  return best;
}

const ALERT_SEVERITY_COLOR: Record<Alert["severity"], string> = {
  info: "var(--color-trust-green)",
  warning: "var(--color-trust-amber)",
  critical: "var(--color-trust-red)",
};

const ALERTS_POLL_MS = 20_000;

const PUBLIC_MESSAGE: Record<TrustLabel, { title: string; body: string }> = {
  green: { title: "Safe", body: "The forecast matches real sensor readings at this location." },
  amber: {
    title: "Caution",
    body: "Readings near this location differ somewhat from the forecast. Check conditions before heading out.",
  },
  red: {
    title: "Avoid",
    body: "Real sensors disagree strongly with the forecast near this location. Treat the forecast as unreliable here.",
  },
};

export function DigitalTwin() {
  const [connection, setConnection] = useState<ConnectionState>("checking");
  const [fused, setFused] = useState<FusedResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [engine, setEngine] = useState<"auto" | "gnn" | "fallback">("auto");
  const [mode, setMode] = useState<Mode>("expert");
  const [center, setCenter] = useState(REGION_CENTER);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [alerts, setAlerts] = useState<Alert[] | null>(null);
  const [alertsError, setAlertsError] = useState<string | null>(null);

  const load = useCallback(async (chosenEngine: "auto" | "gnn" | "fallback") => {
    setError(null);
    try {
      await api.health();
      setConnection("online");
      const response = await api.fused(chosenEngine);
      setFused(response);
    } catch (err) {
      setConnection("offline");
      setError(err instanceof ApiError ? err.message : "Unexpected error reaching the backend.");
    }
  }, []);

  useEffect(() => {
    load(engine);
  }, [engine, load]);

  // Person 2's Drift Memory Engine is a separate, optional process -- its
  // absence shouldn't block the rest of the page (unlike the Graph Fusion
  // Engine above), so failures land in their own `alertsError` state rather
  // than the big red "offline" banner.
  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const response = await driftApi.alerts();
        if (!cancelled) {
          setAlerts(response);
          setAlertsError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setAlertsError(err instanceof ApiError ? err.message : "Unexpected error reaching the Drift Memory Engine.");
        }
      }
    };
    poll();
    const interval = setInterval(poll, ALERTS_POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const markers: GlobeMarker[] =
    fused?.points.filter((p) => p.is_sensor_node).map((p) => ({
      id: pointId(p),
      lat: p.lat,
      lon: p.lon,
      label: `${p.sst_c?.toFixed(1) ?? "N/A"}°C`,
      detail: `confidence ${Math.round(p.confidence * 100)}%`,
      trust: p.trust_label,
      depthM: p.depth_m,
    })) ?? [];

  const selectedPoint: FusedPoint | null = useMemo(() => {
    if (!fused || !selectedId) return null;
    return fused.points.find((p) => pointId(p) === selectedId) ?? null;
  }, [fused, selectedId]);

  const nearbyPoints: FusedPoint[] = useMemo(() => {
    if (!fused || !selectedPoint) return [];
    const inWindow = fused.points.filter(
      (p) =>
        Math.abs(p.lat - selectedPoint.lat) <= NEARBY_WINDOW_DEG &&
        Math.abs(p.lon - selectedPoint.lon) <= NEARBY_WINDOW_DEG,
    );
    if (inWindow.length <= NEARBY_MAX_POINTS) return inWindow;
    // Keep the selected point plus the nearest others if the window is dense.
    const rest = inWindow
      .filter((p) => p !== selectedPoint)
      .sort((a, b) => {
        const da = (a.lat - selectedPoint.lat) ** 2 + (a.lon - selectedPoint.lon) ** 2;
        const db = (b.lat - selectedPoint.lat) ** 2 + (b.lon - selectedPoint.lon) ** 2;
        return da - db;
      })
      .slice(0, NEARBY_MAX_POINTS - 1);
    return [selectedPoint, ...rest];
  }, [fused, selectedPoint]);

  return (
    <div className="mx-auto max-w-7xl px-6 py-28">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="font-nav text-xs opacity-60">Live · {REGION_LABEL}</p>
          <h1 className="font-display mt-2 text-4xl sm:text-5xl">Digital Twin</h1>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="flex rounded-full border p-1" style={{ borderColor: "var(--color-border)" }}>
            {(["expert", "public"] as Mode[]).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className="font-nav rounded-full px-4 py-1.5 text-xs capitalize"
                style={mode === m ? { backgroundColor: "var(--color-ink)", color: "var(--color-bg)" } : undefined}
              >
                {m}
              </button>
            ))}
          </div>
          <select
            value={engine}
            onChange={(e) => setEngine(e.target.value as typeof engine)}
            className="font-nav rounded-full border bg-transparent px-4 py-1.5 text-xs"
            style={{ borderColor: "var(--color-border)" }}
          >
            <option value="auto">Engine: auto</option>
            <option value="gnn">Engine: GNN</option>
            <option value="fallback">Engine: fallback</option>
          </select>
        </div>
      </div>

      {connection === "offline" && (
        <div
          className="mt-8 rounded-xl border px-5 py-4 text-sm"
          style={{ borderColor: "var(--color-trust-red)", color: "var(--color-trust-red)" }}
        >
          Can't reach the Graph Fusion Engine at <code className="font-mono-data">{API_BASE_URL}</code>.
          {" "}
          {error} Run{" "}
          <code className="font-mono-data">uvicorn graph_fusion.api:app --reload --port 8000</code>{" "}
          from <code className="font-mono-data">varuna-graph-fusion/</code> and reload this page.
        </div>
      )}

      <div className="relative mt-12 grid gap-12 lg:grid-cols-[1fr_1fr]">
        <AnnotationLayer
          items={[
            {
              x: 9,
              y: 2,
              dx: 12,
              dy: 4,
              text: "Drag to rotate, or click the ocean to unwrap it into a flat map",
            },
            {
              x: 20,
              y: 76,
              dx: 9,
              dy: -9,
              text: "Green / amber / red: how closely the model agrees with real sensors here",
            },
            {
              x: 57,
              y: 82,
              dx: 8,
              dy: 1.5,
              text: "Live output from the real Graph Fusion Engine, not pre-recorded",
            },
          ]}
        />
        <div className="flex flex-col items-center gap-4">
          <Globe
            focus={REGION_CENTER}
            markers={markers}
            regionBBox={REGION_BBOX}
            onCenterChange={setCenter}
            onMarkerClick={setSelectedId}
            selectedId={selectedId}
            className="w-full max-w-[520px]"
          />
          <CoordinateReadout label="Viewing" lat={center.lat} lon={center.lon} className="opacity-70" />
          {fused && (
            <div className="flex flex-wrap justify-center gap-4 text-xs opacity-70">
              {(["green", "amber", "red"] as TrustLabel[]).map((label) => (
                <span key={label} className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full" style={{ backgroundColor: TRUST_COLOR[label] }} />
                  {label}
                </span>
              ))}
            </div>
          )}
          <p className="max-w-[520px] text-center text-xs opacity-50">
            Click any point to inspect it, or click the ocean itself (or the corner button) to
            unwrap the globe into a flat map of the region without losing depth: each sensor's
            stem keeps sticking out of the map in real 3D, something a flat 2D map can't show.
          </p>
        </div>

        <div>
          {mode === "public" && fused && (() => {
            const nearest = nearestPoint(fused.points, center);
            const label = nearest?.trust_label ?? "amber";
            return (
              <div className="rounded-2xl border p-8" style={{ borderColor: TRUST_COLOR[label] }}>
                <h2 className="font-display text-3xl" style={{ color: TRUST_COLOR[label] }}>
                  {PUBLIC_MESSAGE[label].title}
                </h2>
                <p className="mt-3 text-sm opacity-80">{PUBLIC_MESSAGE[label].body}</p>
                <p className="mt-4 font-mono-data text-xs opacity-50">
                  Nearest fused point: {nearest ? `${nearest.lat.toFixed(2)}, ${nearest.lon.toFixed(2)}` : "n/a"}
                  {" · "}
                  {fused.summary.n_sensors} real sensors, engine: {fused.summary.engine}.
                </p>
                <p className="mt-2 text-xs opacity-50">
                  Drag the globe to check a different spot in the Bay of Bengal.
                </p>
              </div>
            );
          })()}

          {mode === "expert" && fused && (
            <div>
              <h2 className="font-nav text-xs opacity-60">Fusion summary</h2>
              <dl className="mt-4 grid grid-cols-2 gap-4 text-sm sm:grid-cols-3">
                <div>
                  <dt className="opacity-50">Engine</dt>
                  <dd className="font-mono-data">{fused.summary.engine}</dd>
                </div>
                <div>
                  <dt className="opacity-50">Sensors</dt>
                  <dd className="font-mono-data">{fused.summary.n_sensors}</dd>
                </div>
                <div>
                  <dt className="opacity-50">Grid points</dt>
                  <dd className="font-mono-data">{fused.summary.n_grid_points}</dd>
                </div>
                <div>
                  <dt className="opacity-50">Graph edges</dt>
                  <dd className="font-mono-data">{fused.summary.n_graph_edges}</dd>
                </div>
                <div>
                  <dt className="opacity-50">Mean confidence</dt>
                  <dd className="font-mono-data">{Math.round(fused.summary.mean_confidence * 100)}%</dd>
                </div>
                <div>
                  <dt className="opacity-50">Runtime</dt>
                  <dd className="font-mono-data">{fused.summary.runtime_ms.toFixed(1)} ms</dd>
                </div>
              </dl>

              <h2 className="font-nav mt-10 text-xs opacity-60">
                Sensor-anchored points ({markers.length})
              </h2>
              <p className="mt-1 text-xs opacity-40">
                Trust scale: green ≥ {TRUST_GREEN_MIN * 100}%, amber ≥ {TRUST_AMBER_MIN * 100}%, red below.
              </p>
              <div className="mt-4 max-h-96 space-y-2 overflow-y-auto pr-2">
                {fused.points
                  .filter((p) => p.is_sensor_node)
                  .map((p) => (
                    <button
                      key={pointId(p)}
                      onClick={() => setSelectedId(pointId(p))}
                      className="flex w-full items-center justify-between gap-3 border-b py-2 text-left text-sm transition-opacity hover:opacity-70"
                      style={{ borderColor: "var(--color-border)" }}
                    >
                      <span className="font-mono-data opacity-70">
                        {p.lat.toFixed(2)}, {p.lon.toFixed(2)}
                      </span>
                      <span className="opacity-70">{p.sst_c?.toFixed(2) ?? "N/A"}°C</span>
                      <TrustBadge label={p.trust_label} confidence={p.confidence} />
                    </button>
                  ))}
              </div>
            </div>
          )}

          <div className="mt-12 border-t pt-8" style={{ borderColor: "var(--color-border)" }}>
            <h2 className="font-nav text-xs opacity-60">
              Live alert feed {alerts && alerts.length > 0 ? `(${alerts.length})` : ""}
            </h2>
            {alertsError && (
              <p className="mt-3 text-sm" style={{ color: "var(--color-trust-red)" }}>
                Can't reach the Drift Memory Engine at <code className="font-mono-data">{DRIFT_API_BASE_URL}</code>.
                {" "}
                {alertsError}
              </p>
            )}
            {!alertsError && alerts && alerts.length === 0 && (
              <p className="mt-3 text-sm opacity-60">No active drift alerts right now.</p>
            )}
            {!alertsError && alerts && alerts.length > 0 && (
              <div className="mt-4 max-h-80 space-y-3 overflow-y-auto pr-2">
                {alerts.map((a) => (
                  <div key={a.id} className="border-b pb-3 text-sm" style={{ borderColor: "var(--color-border)" }}>
                    <div className="flex items-center gap-2">
                      <span
                        className="h-2 w-2 rounded-full"
                        style={{ backgroundColor: ALERT_SEVERITY_COLOR[a.severity] }}
                      />
                      <span className="font-nav text-xs uppercase opacity-60">{a.severity}</span>
                      <span className="font-mono-data text-xs opacity-40">
                        {a.lat.toFixed(2)}, {a.lon.toFixed(2)}
                      </span>
                    </div>
                    <p className="mt-1 opacity-80">{a.message}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {selectedPoint && (
        <PointInspector point={selectedPoint} nearby={nearbyPoints} onClose={() => setSelectedId(null)} />
      )}
    </div>
  );
}
