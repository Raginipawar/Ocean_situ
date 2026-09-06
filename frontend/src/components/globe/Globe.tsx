import { geoOrthographic, geoPath, geoGraticule10, geoDistance } from "d3-geo";
import { feature, mesh } from "topojson-client";
import { useEffect, useMemo, useRef, useState } from "react";
import type { Topology, GeometryCollection } from "topojson-specification";
import worldTopology from "../../assets/geo/countries-110m.json";
import { useTheme } from "../../theme/ThemeProvider";

export interface GlobeMarker {
  lat: number;
  lon: number;
  label: string;
  detail?: string;
  color?: string;
}

interface RegionBBox {
  latMin: number;
  latMax: number;
  lonMin: number;
  lonMax: number;
}

interface GlobeProps {
  size?: number;
  /** Geographic point the globe starts centred on. */
  focus: { lat: number; lon: number };
  markers?: GlobeMarker[];
  /** Draws the real scope-lock bounding box from lib/config.ts as a highlighted outline. */
  regionBBox?: RegionBBox;
  className?: string;
  onCenterChange?: (center: { lat: number; lon: number }) => void;
}

function bboxRing({ latMin, latMax, lonMin, lonMax }: RegionBBox, steps = 24) {
  const coords: [number, number][] = [];
  for (let i = 0; i <= steps; i++) coords.push([lonMin + ((lonMax - lonMin) * i) / steps, latMin]);
  for (let i = 0; i <= steps; i++) coords.push([lonMax, latMin + ((latMax - latMin) * i) / steps]);
  for (let i = 0; i <= steps; i++) coords.push([lonMax - ((lonMax - lonMin) * i) / steps, latMax]);
  for (let i = 0; i <= steps; i++) coords.push([lonMin, latMax - ((latMax - latMin) * i) / steps]);
  return { type: "Polygon" as const, coordinates: [coords] };
}

const AUTO_ROTATE_DEG_PER_SEC = 3.2;
const IDLE_RESUME_MS = 1800;

function normalizeLon(lon: number): number {
  let l = lon % 360;
  if (l > 180) l -= 360;
  if (l < -180) l += 360;
  return l;
}

export function Globe({ size = 560, focus, markers = [], regionBBox, className, onCenterChange }: GlobeProps) {
  const { theme } = useTheme();
  const [rotation, setRotation] = useState<[number, number]>([-focus.lon, -focus.lat]);
  const [isDragging, setIsDragging] = useState(false);
  const draggingRef = useRef(false);
  const lastPointerRef = useRef<{ x: number; y: number } | null>(null);
  const lastInteractionRef = useRef(0);
  const rafRef = useRef<number | null>(null);

  const topology = worldTopology as unknown as Topology;
  const land = useMemo(
    () => feature(topology, topology.objects.land as GeometryCollection),
    [topology],
  );
  const borders = useMemo(
    () =>
      mesh(topology, topology.objects.countries as GeometryCollection, (a, b) => a !== b),
    [topology],
  );
  const graticule = useMemo(() => geoGraticule10(), []);
  const bboxRingGeometry = useMemo(() => (regionBBox ? bboxRing(regionBBox) : null), [regionBBox]);

  const projection = useMemo(
    () =>
      geoOrthographic()
        .scale(size / 2.18)
        .translate([size / 2, size / 2])
        .rotate([rotation[0], rotation[1]])
        .clipAngle(90),
    [size, rotation],
  );

  const path = useMemo(() => geoPath(projection), [projection]);

  useEffect(() => {
    const center = { lat: -rotation[1], lon: normalizeLon(-rotation[0]) };
    onCenterChange?.(center);
  }, [rotation, onCenterChange]);

  useEffect(() => {
    let last = performance.now();

    function tick(now: number) {
      const dt = (now - last) / 1000;
      last = now;
      const idle = now - lastInteractionRef.current > IDLE_RESUME_MS;
      if (idle && !draggingRef.current) {
        setRotation(([lambda, phi]) => [lambda + AUTO_ROTATE_DEG_PER_SEC * dt, phi]);
      }
      rafRef.current = requestAnimationFrame(tick);
    }

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!reduceMotion) {
      rafRef.current = requestAnimationFrame(tick);
    }
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, []);

  function handlePointerDown(e: React.PointerEvent) {
    draggingRef.current = true;
    setIsDragging(true);
    lastPointerRef.current = { x: e.clientX, y: e.clientY };
    (e.target as Element).setPointerCapture(e.pointerId);
  }

  function handlePointerMove(e: React.PointerEvent) {
    lastInteractionRef.current = performance.now();
    if (!draggingRef.current || !lastPointerRef.current) return;
    const dx = e.clientX - lastPointerRef.current.x;
    const dy = e.clientY - lastPointerRef.current.y;
    lastPointerRef.current = { x: e.clientX, y: e.clientY };
    setRotation(([lambda, phi]) => [
      lambda + dx * 0.35,
      Math.max(-90, Math.min(90, phi - dy * 0.35)),
    ]);
  }

  function handlePointerUp() {
    draggingRef.current = false;
    setIsDragging(false);
    lastPointerRef.current = null;
    lastInteractionRef.current = performance.now();
  }

  const isDark = theme === "dark";
  const oceanFill = isDark ? "#0d1926" : "#dcebe8";
  const landFill = isDark ? "#16222c" : "#c9dcd3";
  const borderStroke = isDark ? "rgba(244,234,225,0.18)" : "rgba(20,17,15,0.22)";
  const graticuleStroke = isDark ? "rgba(244,234,225,0.06)" : "rgba(20,17,15,0.08)";

  return (
    <svg
      viewBox={`0 0 ${size} ${size}`}
      width={size}
      height={size}
      className={className}
      role="img"
      aria-label={`Rotating globe centred on ${focus.lat.toFixed(1)}, ${focus.lon.toFixed(1)}`}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerLeave={handlePointerUp}
      style={{ touchAction: "none", cursor: isDragging ? "grabbing" : "grab" }}
    >
      <defs>
        <radialGradient id="globe-atmosphere" cx="50%" cy="42%" r="60%">
          <stop offset="60%" stopColor="var(--color-accent)" stopOpacity="0" />
          <stop offset="92%" stopColor="var(--color-accent)" stopOpacity="0.35" />
          <stop offset="100%" stopColor="var(--color-accent)" stopOpacity="0" />
        </radialGradient>
      </defs>

      <circle
        cx={size / 2}
        cy={size / 2}
        r={size / 2 - 2}
        fill="none"
        stroke="url(#globe-atmosphere)"
        strokeWidth={14}
      />

      <path d={path({ type: "Sphere" }) ?? undefined} fill={oceanFill} />
      <path d={path(graticule) ?? undefined} fill="none" stroke={graticuleStroke} strokeWidth={0.5} />
      <path d={path(land) ?? undefined} fill={landFill} />
      <path d={path(borders) ?? undefined} fill="none" stroke={borderStroke} strokeWidth={0.6} />
      {bboxRingGeometry && (
        <path
          d={path(bboxRingGeometry) ?? undefined}
          fill="var(--color-accent)"
          fillOpacity={0.18}
          stroke="var(--color-accent)"
          strokeWidth={1.5}
        />
      )}
      <path
        d={path({ type: "Sphere" }) ?? undefined}
        fill="none"
        stroke="var(--color-accent)"
        strokeOpacity={0.5}
        strokeWidth={1}
      />

      {markers.map((marker) => {
        const dist = geoDistance([marker.lon, marker.lat], [-rotation[0], -rotation[1]]);
        const visible = dist < Math.PI / 2;
        const projected = projection([marker.lon, marker.lat]);
        if (!visible || !projected) return null;
        const [x, y] = projected;
        const color = marker.color ?? "var(--color-accent)";
        return (
          <g key={`${marker.label}-${marker.lat}-${marker.lon}`} transform={`translate(${x}, ${y})`}>
            <title>{marker.detail ? `${marker.label} — ${marker.detail}` : marker.label}</title>
            <circle r={7} fill={color} opacity={0.25}>
              <animate attributeName="r" values="4;11;4" dur="2.4s" repeatCount="indefinite" />
              <animate attributeName="opacity" values="0.45;0;0.45" dur="2.4s" repeatCount="indefinite" />
            </circle>
            <circle r={3} fill={color} />
          </g>
        );
      })}
    </svg>
  );
}
