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
        <rect width={MAP_SIZE} height={MAP_SIZE} fill="var(--color-surface-2, var(--color-surface))" />
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
                    <span>{row.value !== null ? `${row.value.toFixed(row.decimals)} ${row.unit}` : "—"}</span>
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
          </div>
        </div>
      </div>
    </div>
  );
}
