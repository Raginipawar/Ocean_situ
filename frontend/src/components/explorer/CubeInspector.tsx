import { Canvas, useFrame } from "@react-three/fiber";
import { Html, OrbitControls } from "@react-three/drei";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { sstToColor } from "../../lib/oceanColor";
import type { NowcastInfo } from "../../lib/types";

const CUBE_SIZE = 4.5;

export interface CubeLevelData {
  depth_m: number;
  sst_c: number;
  salinity_psu: number;
  current_u_ms: number;
  current_v_ms: number;
  wave_height_m: number;
  chlorophyll_mg_m3: number;
}

/** Animated water surface -- real vertex-displaced ripples, amplitude and
 * speed driven by the real wave_height_m at this cell. Applied only to the
 * surface slab: sub-surface layers get a still, flat slab on purpose --
 * surface gravity waves are a real-physics surface-only phenomenon, so
 * animating "waves" at 200m depth would misrepresent the data rather than
 * visualize it. */
function WaterSurface({ waveHeightM, color }: { waveHeightM: number; color: string }) {
  const meshRef = useRef<THREE.Mesh>(null);
  const geomArgs = useMemo<[number, number, number, number]>(() => [CUBE_SIZE * 0.94, CUBE_SIZE * 0.94, 24, 24], []);
  const basePositions = useRef<Float32Array | null>(null);
  // Clamp to a legible visual range without altering the real number shown
  // in the label -- a 0.2m and a 4m sea are both "real", but a purely
  // linear amplitude would make the calm one invisible and the rough one
  // absurd at this render scale.
  const amplitude = THREE.MathUtils.clamp(waveHeightM, 0.05, 1.2) * 0.16;

  useFrame(({ clock }) => {
    const mesh = meshRef.current;
    if (!mesh) return;
    const geom = mesh.geometry as THREE.PlaneGeometry;
    const pos = geom.attributes.position as THREE.BufferAttribute;
    if (!basePositions.current) basePositions.current = Float32Array.from(pos.array);
    const base = basePositions.current;
    const t = clock.getElapsedTime() * (0.6 + waveHeightM * 0.3);
    for (let i = 0; i < pos.count; i++) {
      const x = base[i * 3];
      const y = base[i * 3 + 1];
      const z = Math.sin(x * 2.2 + t) * amplitude + Math.cos(y * 1.7 + t * 1.3) * amplitude * 0.6;
      pos.setZ(i, z);
    }
    pos.needsUpdate = true;
    geom.computeVertexNormals();
  });

  return (
    <mesh ref={meshRef} rotation={[-Math.PI / 2, 0, 0]}>
      <planeGeometry args={geomArgs} />
      <meshStandardMaterial color={color} transparent opacity={0.8} side={THREE.DoubleSide} roughness={0.35} metalness={0.1} />
    </mesh>
  );
}

/** A real current vector at this depth: direction from current_u_ms (east)
 * / current_v_ms (north), length scaled by the real speed. */
function CurrentArrow({ u, v, y }: { u: number; v: number; y: number }) {
  const arrow = useMemo(() => {
    const speed = Math.hypot(u, v);
    const dir = speed > 1e-6 ? new THREE.Vector3(u, 0, -v).normalize() : new THREE.Vector3(1, 0, 0);
    const length = THREE.MathUtils.clamp(speed * 1.8, 0.3, CUBE_SIZE * 0.42);
    return new THREE.ArrowHelper(dir, new THREE.Vector3(0, 0, 0), length, 0xf2b134, length * 0.35, length * 0.22);
  }, [u, v]);
  return <primitive object={arrow} position={[0, y, 0]} />;
}

function DepthSlab({ level, y, isSurface }: { level: CubeLevelData; y: number; isSurface: boolean }) {
  const color = sstToColor(level.sst_c);
  return (
    <group position={[0, y, 0]}>
      {isSurface ? (
        <WaterSurface waveHeightM={level.wave_height_m} color={color} />
      ) : (
        <mesh>
          <boxGeometry args={[CUBE_SIZE * 0.94, 0.04, CUBE_SIZE * 0.94]} />
          <meshStandardMaterial color={color} transparent opacity={0.68} />
        </mesh>
      )}
      <CurrentArrow u={level.current_u_ms} v={level.current_v_ms} y={0.04} />
      <Html center distanceFactor={9.5} occlude={false}>
        <div
          className="font-mono-data pointer-events-none whitespace-nowrap rounded px-1.5 py-0.5 text-[8px] leading-[1.15] shadow"
          style={{ backgroundColor: "var(--color-bg)", border: "1px solid var(--color-border)", color: "var(--color-ink)" }}
        >
          <div className="font-nav opacity-60">{isSurface ? "surface" : `${level.depth_m.toFixed(0)}m`}</div>
          <div>{level.sst_c.toFixed(2)}°C</div>
          <div>{level.salinity_psu.toFixed(2)} PSU</div>
          <div>
            u {level.current_u_ms.toFixed(2)} / v {level.current_v_ms.toFixed(2)} m/s
          </div>
          {isSurface && <div>wave {level.wave_height_m.toFixed(2)}m</div>}
        </div>
      </Html>
    </group>
  );
}

function CubeScene({ levels }: { levels: CubeLevelData[] }) {
  return (
    <>
      <ambientLight intensity={1.1} />
      <directionalLight position={[4, 5, 4]} intensity={1.2} />
      {/* The "fixed dimensions cube" itself -- a wireframe box, constant
          size for every real grid cell in the Bay of Bengal. */}
      <lineSegments>
        <edgesGeometry args={[new THREE.BoxGeometry(CUBE_SIZE, CUBE_SIZE, CUBE_SIZE)]} />
        <lineBasicMaterial color="#79a4c0" />
      </lineSegments>
      {levels.map((level, i) => {
        // Rank-based (not depth-proportional) vertical spacing: real depth
        // levels bunch up near the surface, which crowds labels together
        // under a linear depth->y mapping. Every slab still shows its own
        // real depth_m label in order -- this only changes row height.
        const rank = levels.length > 1 ? i / (levels.length - 1) : 0;
        const y = CUBE_SIZE / 2 - rank * CUBE_SIZE;
        return <DepthSlab key={i} level={level} y={y} isSurface={i === 0} />;
      })}
      <OrbitControls enablePan={false} minDistance={4.5} maxDistance={18} />
    </>
  );
}

export interface CubeInspectorProps {
  lat: number;
  lon: number;
  source: string;
  /** Always the real 10 depth levels for this grid cell, ordered
   * shallow-to-deep, for whichever real day is currently selected. */
  levels: CubeLevelData[];
  /** The real ISO date these levels are for. */
  timeLabel: string;
  /** Real dates available for scrubbing (populated once the full 270-day
   * series for this cell has been fetched) -- null while loading/absent. */
  availableDays: string[] | null;
  selectedDayIndex: number;
  onDayIndexChange: (index: number) => void;
  nowcastInfo: NowcastInfo | null;
  onClose: () => void;
}

export function CubeInspector({
  lat,
  lon,
  source,
  levels,
  timeLabel,
  availableDays,
  selectedDayIndex,
  onDayIndexChange,
  nowcastInfo,
  onClose,
}: CubeInspectorProps) {
  // Arrow-key/Page Up/Down navigation is handled once, globally, by the
  // Explorer page -- it works the same whether or not this modal is open
  // (panning the map, Google-Maps-style, doesn't require a cube to be
  // open first). This component only owns Escape-to-close, since that's
  // specific to the modal being open.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-6"
      style={{ backgroundColor: "rgba(0,0,0,0.55)" }}
      onClick={onClose}
    >
      <div
        className="grid w-full max-w-4xl gap-6 rounded-2xl p-8 shadow-2xl sm:grid-cols-[1fr_320px]"
        style={{ backgroundColor: "var(--color-bg)", border: "1px solid var(--color-border)" }}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div>
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="font-nav text-xs opacity-60">Real volumetric cube · {timeLabel}</p>
              <h2 className="font-display mt-1 text-2xl">
                {lat.toFixed(3)}°N, {lon.toFixed(3)}°E
              </h2>
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
          <p className="mt-3 font-mono-data text-[10px] opacity-50">{source}</p>

          <div className="mt-4 h-80 w-full rounded-xl" style={{ border: "1px solid var(--color-border)" }}>
            <Canvas camera={{ position: [6.5, 4.5, 6.5], fov: 45 }}>
              <CubeScene levels={levels} />
            </Canvas>
          </div>

          {availableDays && availableDays.length > 1 && (
            <div className="mt-3">
              <input
                type="range"
                min={0}
                max={availableDays.length - 1}
                value={selectedDayIndex}
                onChange={(e) => onDayIndexChange(Number(e.target.value))}
                className="w-full"
              />
              <p className="mt-1 text-center text-[10px] opacity-50">
                {availableDays[0]} — real day {selectedDayIndex + 1} of {availableDays.length} — {availableDays[availableDays.length - 1]}
              </p>
            </div>
          )}

          <p className="mt-2 text-xs opacity-40">
            ↑ ↓ ← → to move to the neighboring cube · Page Up/Down for shallower/deeper · Esc to close
          </p>
        </div>

        <div>
          <h3 className="font-nav text-xs opacity-60">Nowcast Engine (Person 3)</h3>
          {nowcastInfo?.available ? (
            <div className="mt-3 space-y-2 text-xs">
              <p className="opacity-70">{nowcastInfo.architecture}</p>
              <p className="font-mono-data opacity-70">{nowcastInfo.n_parameters?.toLocaleString()} parameters</p>
              <p className="opacity-70">{nowcastInfo.trained_on}</p>
              {nowcastInfo.improvement_over_baseline_pct !== null && (
                <p className="font-mono-data" style={{ color: "var(--color-trust-green)" }}>
                  {nowcastInfo.improvement_over_baseline_pct!.toFixed(1)}% better than persistence baseline
                </p>
              )}
              <p className="mt-2 text-[10px] opacity-40">{nowcastInfo.note}</p>
            </div>
          ) : (
            <p className="mt-3 text-xs opacity-50">{nowcastInfo ? nowcastInfo.note : "Nowcast Engine info unavailable."}</p>
          )}
        </div>
      </div>
    </div>
  );
}
