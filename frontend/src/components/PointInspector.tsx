import { useEffect, useMemo } from "react";
import { TrustBadge } from "./TrustBadge";
import type { FusedPoint } from "../lib/types";

const TRUST_COLOR: Record<FusedPoint["trust_label"], string> = {
  green: "var(--color-trust-green)",
  amber: "var(--color-trust-amber)",
  red: "var(--color-trust-red)",
};

/** How far out (degrees) the local mini-map looks around the selected point. */
const MAP_WINDOW_DEG = 3;
const MAP_SIZE = 220;
const PROFILE_WIDTH = 220;
const PROFILE_HEIGHT = 160;
const PROFILE_PAD = 28;

interface VariableRow {
  label: string;
  unit: string;
  value: number | null;
  correction: number | null;
  decimals: number;
}

function variableRows(p: FusedPoint): VariableRow[] {
  return [
    { label: "Sea surface temperature", unit: "°C", value: p.sst_c, correction: p.correction_sst_c, decimals: 2 },
    { label: "Current (east-west)", unit: "m/s", value: p.current_u_ms, correction: p.correction_current_u_ms, decimals: 3 },
    { label: "Current (north-south)", unit: "m/s", value: p.current_v_ms, correction: p.correction_current_v_ms, decimals: 3 },
    { label: "Wave height", unit: "m", value: p.wave_height_m, correction: p.correction_wave_height_m, decimals: 2 },
  ];
}

/** Simple local scatter map (plain SVG, no map library) of the points near
 * the selected one, colour-coded by trust -- this IS the "map of that
 * particular [point]" the click is meant to expand into: spatial context
 * for whether the disagreement here is an isolated blip or part of a
 * regional pattern. */
function LocalMiniMap({ center, nearby }: { center: FusedPoint; nearby: FusedPoint[] }) {
  const latMin = center.lat - MAP_WINDOW_DEG;
  const latMax = center.lat + MAP_WINDOW_DEG;
  const lonMin = center.lon - MAP_WINDOW_DEG;
  const lonMax = center.lon + MAP_WINDOW_DEG;

  const toXY = (lat: number, lon: number) => {
    const x = ((lon - lonMin) / (lonMax - lonMin)) * MAP_SIZE;
    const y = ((latMax - lat) / (latMax - latMin)) * MAP_SIZE; // lat increases upward
    return [x, y] as const;
  };

  return (
    <div>
      <svg
        width={MAP_SIZE}
        height={MAP_SIZE}
        viewBox={`0 0 ${MAP_SIZE} ${MAP_SIZE}`}
        role="img"
        aria-label={`Local map around ${center.lat.toFixed(2)}, ${center.lon.toFixed(2)}`}
        style={{ borderRadius: 12, border: "1px solid var(--color-border)" }}
      >
        <rect width={MAP_SIZE} height={MAP_SIZE} fill="var(--color-bg-raised)" />
        {nearby.map((p, i) => {
          const [x, y] = toXY(p.lat, p.lon);
          const isCenter = p.lat === center.lat && p.lon === center.lon;
          return (
            <circle
              key={i}
              cx={x}
              cy={y}
              r={isCenter ? 6 : p.is_sensor_node ? 3.5 : 2.5}
              fill={TRUST_COLOR[p.trust_label]}
              stroke={isCenter ? "var(--color-ink)" : "none"}
              strokeWidth={isCenter ? 2 : 0}
              opacity={isCenter ? 1 : 0.75}
            />
          );
        })}
      </svg>
      <div className="mt-2 flex items-center justify-between font-mono-data text-[10px] opacity-50">
        <span>{lonMin.toFixed(1)}°E</span>
        <span>±{MAP_WINDOW_DEG}° window</span>
        <span>{lonMax.toFixed(1)}°E</span>
      </div>
    </div>
  );
}

/**
 * SST-vs-depth scatter of real sensors near the selected point -- the one
 * view a flat 2D map genuinely cannot show, since it only ever colours a
 * surface. This is NOT a single Argo float's vertical profile (the mock
 * backend gives each sensor exactly one depth, not a depth-stacked cast at
 * one location -- see mock_data.py's depth_choices), so it's labelled as
 * what it actually is: real depth/temperature readings from different
 * nearby sensors, not one continuous curve.
 */
function DepthProfileChart({ point, nearby }: { point: FusedPoint; nearby: FusedPoint[] }) {
  const withDepth = useMemo(
    () => nearby.filter((p) => p.is_sensor_node && p.sst_c !== null),
    [nearby],
  );

  if (withDepth.length < 2) return null;

  const depths = withDepth.map((p) => p.depth_m);
  const temps = withDepth.map((p) => p.sst_c as number);
  const maxDepth = Math.max(10, ...depths);
  const minTemp = Math.min(...temps);
  const maxTemp = Math.max(...temps);
  const tempSpan = Math.max(0.5, maxTemp - minTemp);

  const plotW = PROFILE_WIDTH - PROFILE_PAD;
  const plotH = PROFILE_HEIGHT - PROFILE_PAD;

  const toXY = (depthM: number, sstC: number) => {
    const x = PROFILE_PAD + ((sstC - minTemp) / tempSpan) * plotW;
    const y = (depthM / maxDepth) * plotH; // 0m at top, deeper sinks down
    return [x, y] as const;
  };

  return (
    <div>
      <svg
        width={PROFILE_WIDTH}
        height={PROFILE_HEIGHT}
        viewBox={`0 0 ${PROFILE_WIDTH} ${PROFILE_HEIGHT}`}
        role="img"
        aria-label="Sea surface temperature by depth for nearby real sensors"
        style={{ borderRadius: 12, border: "1px solid var(--color-border)" }}
      >
        <rect width={PROFILE_WIDTH} height={PROFILE_HEIGHT} fill="var(--color-bg-raised)" />
        <line
          x1={PROFILE_PAD}
          y1={0}
          x2={PROFILE_PAD}
          y2={plotH}
          stroke="var(--color-border)"
          strokeWidth={1}
        />
        {withDepth.map((p, i) => {
          const [x, y] = toXY(p.depth_m, p.sst_c as number);
          const isSelected = p.lat === point.lat && p.lon === point.lon;
          return (
            <circle
              key={i}
              cx={x}
              cy={y}
              r={isSelected ? 6 : 3.5}
              fill={TRUST_COLOR[p.trust_label]}
              stroke={isSelected ? "var(--color-ink)" : "none"}
              strokeWidth={isSelected ? 2 : 0}
              opacity={isSelected ? 1 : 0.75}
            />
          );
        })}
      </svg>
      <div className="mt-2 flex items-center justify-between font-mono-data text-[10px] opacity-50">
        <span>0m</span>
        <span>SST vs. depth, nearby sensors</span>
        <span>{Math.round(maxDepth)}m</span>
      </div>
    </div>
  );
}

export function PointInspector({
  point,
  nearby,
  onClose,
}: {
  point: FusedPoint;
  nearby: FusedPoint[];
  onClose: () => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const rows = useMemo(() => variableRows(point), [point]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-6"
      style={{ backgroundColor: "rgba(0,0,0,0.45)" }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl rounded-2xl p-8 shadow-2xl"
        style={{ backgroundColor: "var(--color-bg)", border: "1px solid var(--color-border)" }}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="font-nav text-xs opacity-60">
              {point.is_sensor_node ? "Real sensor node" : "Fused grid point"}
            </p>
            <h2 className="font-display mt-1 text-2xl">
              {point.lat.toFixed(3)}°N, {point.lon.toFixed(3)}°E
            </h2>
            {point.depth_m > 0 && <p className="mt-1 text-xs opacity-50">Depth: {point.depth_m}m</p>}
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="font-nav rounded-full border px-3 py-1.5 text-xs"
            style={{ borderColor: "var(--color-border)" }}
          >
            Close ✕
          </button>
        </div>

        <div className="mt-4">
          <TrustBadge label={point.trust_label} confidence={point.confidence} />
        </div>

        <div className="mt-6 grid gap-8 sm:grid-cols-[1fr_auto]">
          <div>
            <h3 className="font-nav text-xs opacity-60">Readings vs. model correction</h3>
            <dl className="mt-3 space-y-3">
              {rows.map((row) => (
                <div key={row.label} className="flex items-center justify-between gap-4 text-sm">
                  <dt className="opacity-70">{row.label}</dt>
                  <dd className="font-mono-data flex items-center gap-3">
                    <span>{row.value !== null ? `${row.value.toFixed(row.decimals)} ${row.unit}` : "N/A"}</span>
                    {row.correction !== null && (
                      <span
                        className="text-xs opacity-70"
                        style={{ color: row.correction >= 0 ? "var(--color-trust-red)" : "var(--color-trust-green)" }}
                      >
                        ({row.correction >= 0 ? "+" : ""}
                        {row.correction.toFixed(row.decimals)})
                      </span>
                    )}
                  </dd>
                </div>
              ))}
            </dl>
            <p className="mt-4 text-xs opacity-50">
              Support (nearby real-sensor evidence backing this point): {Math.round(point.support * 100)}%
            </p>
          </div>

          <div>
            <h3 className="font-nav text-xs opacity-60">Local area</h3>
            <div className="mt-3">
              <LocalMiniMap center={point} nearby={nearby} />
            </div>
            <h3 className="font-nav mt-6 text-xs opacity-60">Depth</h3>
            <div className="mt-3">
              <DepthProfileChart point={point} nearby={nearby} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
