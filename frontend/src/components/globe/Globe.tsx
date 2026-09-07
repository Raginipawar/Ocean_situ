import { OrbitControls, Line, Stars, useTexture } from "@react-three/drei";
import { Canvas, useFrame, useThree, type ThreeEvent } from "@react-three/fiber";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import earthDayMap from "../../assets/textures/earth_daymap.jpg";
import earthNightMap from "../../assets/textures/earth_nightmap.jpg";
import earthCloudsMap from "../../assets/textures/earth_clouds.jpg";
import { useTheme } from "../../theme/ThemeProvider";

export type TrustLabel = "green" | "amber" | "red";

export interface GlobeMarker {
  /** Stable identity for click/selection correlation back to the caller's own data. */
  id: string;
  lat: number;
  lon: number;
  label: string;
  detail?: string;
  /**
   * Real reported sensor depth in metres (0 = surface). When set, a short
   * stem is drawn from the surface point down into the globe -- a literal
   * third dimension a flat 2D map pin can't show. The stem length is
   * visually exaggerated (real depths of a few hundred metres are
   * imperceptible against Earth's radius), the same "vertical exaggeration"
   * concept the approach doc calls for elsewhere, not a to-scale depth.
   */
  depthM?: number;
  /** Preferred: resolved theme-aware color internally (see TRUST_HEX below). */
  trust?: TrustLabel;
  /**
   * Escape hatch for a literal color. Must be a value Three.js's Color
   * parser understands (hex like "#2ecc71", or an rgb()/named color) --
   * NOT a CSS custom property reference. `var(--color-trust-green)` is
   * only resolvable by the DOM/CSSOM; passed straight into a WebGL
   * material it fails to parse and silently renders white. If you need a
   * value driven by index.css, resolve it there and pass the hex string.
   */
  color?: string;
}

// Mirrors index.css's --color-trust-* light/dark values exactly. Kept in
// sync manually (same pattern as lib/config.ts mirroring the backend) since
// a WebGL material color can't read a CSS custom property directly.
const TRUST_HEX: Record<"light" | "dark", Record<TrustLabel, string>> = {
  light: { green: "#1f8a5f", amber: "#b9770e", red: "#c1402f" },
  dark: { green: "#3ddc97", amber: "#f2b134", red: "#ef5350" },
};

interface RegionBBox {
  latMin: number;
  latMax: number;
  lonMin: number;
  lonMax: number;
}

interface GlobeProps {
  /** Geographic point the camera starts facing. */
  focus: { lat: number; lon: number };
  markers?: GlobeMarker[];
  /** Draws the real scope-lock bounding box from lib/config.ts as a highlighted outline. */
  regionBBox?: RegionBBox;
  className?: string;
  onCenterChange?: (center: { lat: number; lon: number }) => void;
  /** Click-to-inspect: fires with the clicked marker's id. */
  onMarkerClick?: (id: string) => void;
  /** id of the currently-selected marker, if any -- drawn larger/brighter. */
  selectedId?: string | null;
  /** Click-to-unwrap into a flat map. Defaults on; the home page hero turns
   * it off since that globe is a decorative preview, not the inspection
   * tool the Digital Twin page's version is. */
  enableFlatten?: boolean;
}

const EARTH_RADIUS = 1;
const CAMERA_DISTANCE = 3.1;
const MARKER_SURFACE_RADIUS = EARTH_RADIUS * 1.015;

/** Size (in scene units) of the flattened equirectangular plane the globe
 * unwraps into on click -- a classic 2:1 map aspect. Picked so it's roughly
 * the same scale as the sphere's own circumference, so the "unwrap" reads
 * as a continuous transformation rather than a sudden resize. */
const FLAT_WIDTH = 4;
const FLAT_HEIGHT = 2;
const EXPAND_DURATION = 1.15;

interface Transition {
  startTime: number;
  fromMorph: number;
  toMorph: number;
  fromCamPos: THREE.Vector3;
  toCamPos: THREE.Vector3;
  fromTarget: THREE.Vector3;
  toTarget: THREE.Vector3;
}

function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2;
}

/** Standard lat/lon -> sphere-surface conversion matching a default equirectangular map on a three.js SphereGeometry. */
function latLonToVector3(lat: number, lon: number, radius: number): THREE.Vector3 {
  const phi = (90 - lat) * (Math.PI / 180);
  const theta = (lon + 180) * (Math.PI / 180);
  return new THREE.Vector3(
    -radius * Math.sin(phi) * Math.cos(theta),
    radius * Math.cos(phi),
    radius * Math.sin(phi) * Math.sin(theta),
  );
}

/** Same lat/lon, projected onto the flattened plane. Kept as the exact
 * inverse-consistent counterpart of latLonToVector3 (both derived from the
 * same phi/theta convention) so a marker's flat position always lines up
 * with where the unwrapped globe shader puts that same point -- see the
 * matching GLSL in injectMorphIntoMaterial below. */
function latLonToFlatVector3(lat: number, lon: number, z = 0): THREE.Vector3 {
  const x = (lon / 360) * FLAT_WIDTH;
  const y = (lat / 90) * (FLAT_HEIGHT / 2);
  return new THREE.Vector3(x, y, z);
}

function vector3ToLatLon(v: THREE.Vector3): { lat: number; lon: number } {
  const r = v.length();
  const phi = Math.acos(THREE.MathUtils.clamp(v.y / r, -1, 1));
  const theta = Math.atan2(v.z, -v.x);
  const rawLon = theta * (180 / Math.PI) - 180;
  return {
    lat: 90 - phi * (180 / Math.PI),
    lon: ((rawLon + 180) % 360 + 360) % 360 - 180,
  };
}

function bboxRingPoints(bbox: RegionBBox, radius: number, steps = 24): [number, number, number][] {
  const { latMin, latMax, lonMin, lonMax } = bbox;
  const ring: [number, number, number][] = [];
  const push = (lat: number, lon: number) => {
    const p = latLonToVector3(lat, lon, radius);
    ring.push([p.x, p.y, p.z]);
  };
  for (let i = 0; i <= steps; i++) push(latMin, lonMin + ((lonMax - lonMin) * i) / steps);
  for (let i = 0; i <= steps; i++) push(latMin + ((latMax - latMin) * i) / steps, lonMax);
  for (let i = 0; i <= steps; i++) push(latMax, lonMax - ((lonMax - lonMin) * i) / steps);
  for (let i = 0; i <= steps; i++) push(latMax - ((latMax - latMin) * i) / steps, lonMin);
  return ring;
}

function flatBboxRingPoints(bbox: RegionBBox, steps = 24): [number, number, number][] {
  const { latMin, latMax, lonMin, lonMax } = bbox;
  const ring: [number, number, number][] = [];
  const push = (lat: number, lon: number) => {
    const p = latLonToFlatVector3(lat, lon, 0.003);
    ring.push([p.x, p.y, p.z]);
  };
  for (let i = 0; i <= steps; i++) push(latMin, lonMin + ((lonMax - lonMin) * i) / steps);
  for (let i = 0; i <= steps; i++) push(latMin + ((latMax - latMin) * i) / steps, lonMax);
  for (let i = 0; i <= steps; i++) push(latMax, lonMax - ((lonMax - lonMin) * i) / steps);
  for (let i = 0; i <= steps; i++) push(latMax - ((latMax - latMin) * i) / steps, lonMin);
  return ring;
}

/**
 * Injects a position/normal morph into a MeshStandardMaterial's compiled
 * shader: mixes the sphere vertex toward its flattened-map equivalent by
 * `uMorph` (0 = globe, 1 = flat). The flat position is derived from the
 * vertex's own local position via the *same* lat/lon convention as
 * latLonToVector3/latLonToFlatVector3 above (re-derived in GLSL, not read
 * from UVs) so the unwrapped texture is guaranteed to line up with where
 * the JS-side markers/bbox place themselves in flat space.
 */
function injectMorphIntoMaterial(material: THREE.Material, morphUniform: { value: number }) {
  if (material.userData.morphInjected) return;
  material.userData.morphInjected = true;
  (material as THREE.MeshStandardMaterial).onBeforeCompile = (shader) => {
    shader.uniforms.uMorph = morphUniform;
    shader.vertexShader = `uniform float uMorph;\n${shader.vertexShader}`
      .replace(
        "#include <beginnormal_vertex>",
        `#include <beginnormal_vertex>
        objectNormal = mix(objectNormal, vec3(0.0, 0.0, 1.0), uMorph);`,
      )
      .replace(
        "#include <begin_vertex>",
        `#include <begin_vertex>
        {
          float r = length(position);
          float phi = acos(clamp(position.y / r, -1.0, 1.0));
          float theta = atan(position.z, -position.x);
          float latDeg = 90.0 - phi * 180.0 / 3.14159265359;
          float lonRaw = theta * 180.0 / 3.14159265359 - 180.0;
          float lonDeg = mod(lonRaw + 180.0, 360.0) - 180.0;
          float flatX = (lonDeg / 360.0) * ${FLAT_WIDTH.toFixed(3)};
          float flatY = (latDeg / 90.0) * ${(FLAT_HEIGHT / 2).toFixed(3)};
          vec3 flatPosition = vec3(flatX, flatY, 0.0);
          transformed = mix(transformed, flatPosition, uMorph);
        }`,
      );
  };
  material.needsUpdate = true;
}

function EarthMesh({
  morphUniform,
  onSurfaceClick,
}: {
  morphUniform: { value: number };
  onSurfaceClick: (e: ThreeEvent<MouseEvent>) => void;
}) {
  const [dayMap, nightMap, cloudsMap] = useTexture([earthDayMap, earthNightMap, earthCloudsMap]);

  useEffect(() => {
    [dayMap, nightMap, cloudsMap].forEach((tex) => {
      tex.colorSpace = THREE.SRGBColorSpace;
      tex.anisotropy = 4;
    });
  }, [dayMap, nightMap, cloudsMap]);

  const cloudsRef = useRef<THREE.Mesh>(null);
  const cloudsMaterialRef = useRef<THREE.MeshStandardMaterial | null>(null);

  useFrame((_, delta) => {
    const settledOnGlobe = 1 - morphUniform.value;
    if (cloudsRef.current) cloudsRef.current.rotation.y += delta * 0.018 * settledOnGlobe;
    if (cloudsMaterialRef.current) cloudsMaterialRef.current.opacity = 0.35 * settledOnGlobe;
  });

  const setSurfaceMaterial = useCallback(
    (m: THREE.MeshStandardMaterial | null) => {
      if (m) injectMorphIntoMaterial(m, morphUniform);
    },
    [morphUniform],
  );
  const setCloudsMaterial = useCallback(
    (m: THREE.MeshStandardMaterial | null) => {
      if (!m) return;
      cloudsMaterialRef.current = m;
      injectMorphIntoMaterial(m, morphUniform);
    },
    [morphUniform],
  );

  return (
    <>
      <mesh onClick={onSurfaceClick}>
        <sphereGeometry args={[EARTH_RADIUS, 64, 64]} />
        <meshStandardMaterial
          ref={setSurfaceMaterial}
          map={dayMap}
          emissiveMap={nightMap}
          emissive="#ffe9b3"
          emissiveIntensity={0.35}
          roughness={0.85}
          metalness={0}
        />
      </mesh>
      <mesh ref={cloudsRef} onClick={onSurfaceClick}>
        <sphereGeometry args={[EARTH_RADIUS * 1.008, 64, 64]} />
        <meshStandardMaterial ref={setCloudsMaterial} map={cloudsMap} transparent opacity={0.35} depthWrite={false} />
      </mesh>
      <mesh onClick={onSurfaceClick}>
        <sphereGeometry args={[EARTH_RADIUS * 1.05, 32, 32]} />
        <shaderMaterial
          side={THREE.BackSide}
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
          uniforms={{ glowColor: { value: new THREE.Color("#79a4c0") }, uMorph: morphUniform }}
          vertexShader={`
            uniform float uMorph;
            varying float intensity;
            void main() {
              float r = length(position);
              float phi = acos(clamp(position.y / r, -1.0, 1.0));
              float theta = atan(position.z, -position.x);
              float latDeg = 90.0 - phi * 180.0 / 3.14159265359;
              float lonRaw = theta * 180.0 / 3.14159265359 - 180.0;
              float lonDeg = mod(lonRaw + 180.0, 360.0) - 180.0;
              float flatX = (lonDeg / 360.0) * ${FLAT_WIDTH.toFixed(3)};
              float flatY = (latDeg / 90.0) * ${(FLAT_HEIGHT / 2).toFixed(3)};
              vec3 flatPosition = vec3(flatX, flatY, 0.05);
              vec3 morphed = mix(position, flatPosition, uMorph);
              vec3 worldPos = (modelMatrix * vec4(morphed, 1.0)).xyz;
              vec3 viewDir = normalize(cameraPosition - worldPos);
              vec3 sphereNormal = normalize(mat3(modelMatrix) * normal);
              vec3 flatNormal = normalize(mat3(modelMatrix) * vec3(0.0, 0.0, 1.0));
              vec3 worldNormal = normalize(mix(sphereNormal, flatNormal, uMorph));
              intensity = pow(0.62 - dot(worldNormal, viewDir), 3.2);
              gl_Position = projectionMatrix * modelViewMatrix * vec4(morphed, 1.0);
            }
          `}
          fragmentShader={`
            varying float intensity;
            uniform vec3 glowColor;
            uniform float uMorph;
            void main() {
              gl_FragColor = vec4(glowColor, clamp(intensity, 0.0, 1.0) * (1.0 - uMorph));
            }
          `}
        />
      </mesh>
    </>
  );
}

function RegionOutline({ regionBBox, morphUniform }: { regionBBox: RegionBBox; morphUniform: { value: number } }) {
  const [mode, setMode] = useState<"sphere" | "flat">("sphere");
  const lastMode = useRef<"sphere" | "flat">("sphere");

  useFrame(() => {
    const next = morphUniform.value > 0.5 ? "flat" : "sphere";
    if (next !== lastMode.current) {
      lastMode.current = next;
      setMode(next);
    }
  });

  const points = useMemo(
    () => (mode === "sphere" ? bboxRingPoints(regionBBox, EARTH_RADIUS * 1.006) : flatBboxRingPoints(regionBBox)),
    [mode, regionBBox],
  );

  return <Line points={points} color="#79a4c0" lineWidth={1.6} />;
}

function Marker({
  marker,
  selected,
  onClick,
  morphUniform,
}: {
  marker: GlobeMarker;
  selected?: boolean;
  onClick?: (id: string) => void;
  morphUniform: { value: number };
}) {
  const { theme } = useTheme();
  const haloRef = useRef<THREE.Mesh>(null);
  const groupRef = useRef<THREE.Group>(null);
  const [hovered, setHovered] = useState(false);
  const [depthMode, setDepthMode] = useState<"sphere" | "flat">("sphere");
  const lastDepthMode = useRef<"sphere" | "flat">("sphere");

  const spherePos = useMemo(
    () => latLonToVector3(marker.lat, marker.lon, MARKER_SURFACE_RADIUS),
    [marker.lat, marker.lon],
  );
  const flatPos = useMemo(() => latLonToFlatVector3(marker.lat, marker.lon), [marker.lat, marker.lon]);

  useFrame(() => {
    if (groupRef.current) groupRef.current.position.lerpVectors(spherePos, flatPos, morphUniform.value);
    const next = morphUniform.value > 0.5 ? "flat" : "sphere";
    if (next !== lastDepthMode.current) {
      lastDepthMode.current = next;
      setDepthMode(next);
    }
  });

  useFrame(({ clock }) => {
    if (!haloRef.current) return;
    const t = (clock.getElapsedTime() * 0.9) % 1;
    haloRef.current.scale.setScalar(1 + t * 2.2);
    (haloRef.current.material as THREE.MeshBasicMaterial).opacity = (selected ? 0.8 : 0.5) * (1 - t);
  });

  useEffect(() => {
    document.body.style.cursor = hovered ? "pointer" : "grab";
    return () => {
      document.body.style.cursor = "grab";
    };
  }, [hovered]);

  // `trust` (theme-resolved here) is preferred; `color` is a literal escape
  // hatch. Either way this must end up a real hex/rgb/named color -- never
  // a CSS var() reference, which Three.js's Color parser can't read and
  // silently renders as white.
  const color = marker.trust ? TRUST_HEX[theme][marker.trust] : (marker.color ?? "#79a4c0");
  const coreRadius = selected ? 0.024 : hovered ? 0.019 : 0.014;

  // Exaggerated on purpose: a real 0-100m sensor depth is imperceptible
  // against a unit-radius globe. Capped so even an unusually deep reading
  // doesn't visually punch through toward the core. Expressed in the
  // marker's own local space (relative to `groupRef`, which is what's
  // sliding between the sphere and flat positions each frame) so the stem
  // rides along with it for free -- only its *direction* needs to flip
  // between "into the globe" and "up off the flattened map", which happens
  // once as the transition crosses its midpoint rather than continuously.
  const depthOffset = marker.depthM && marker.depthM > 0 ? Math.min(marker.depthM * 0.0009, 0.1) : 0;
  const depthLocalEnd = useMemo<[number, number, number] | null>(() => {
    if (!depthOffset) return null;
    if (depthMode === "flat") return [0, 0, depthOffset * 1.6];
    const inward = spherePos.clone().normalize().multiplyScalar(-depthOffset);
    return [inward.x, inward.y, inward.z];
  }, [depthMode, depthOffset, spherePos]);

  return (
    <group ref={groupRef}>
      {depthLocalEnd && (
        <>
          <Line points={[[0, 0, 0], depthLocalEnd]} color={color} lineWidth={1.2} transparent opacity={0.6} />
          <mesh position={depthLocalEnd}>
            <sphereGeometry args={[coreRadius * 0.5, 8, 8]} />
            <meshBasicMaterial color={color} transparent opacity={0.85} depthWrite={false} />
          </mesh>
        </>
      )}
      <mesh
        onClick={(e) => {
          e.stopPropagation();
          onClick?.(marker.id);
        }}
        onPointerOver={(e) => {
          e.stopPropagation();
          setHovered(true);
        }}
        onPointerOut={() => setHovered(false)}
      >
        {/* Slightly larger invisible hit-target so a small dot is still easy to click */}
        <sphereGeometry args={[0.03, 8, 8]} />
        <meshBasicMaterial transparent opacity={0} depthWrite={false} />
      </mesh>
      <mesh>
        <sphereGeometry args={[coreRadius, 14, 14]} />
        <meshBasicMaterial color={color} />
      </mesh>
      {selected && (
        <mesh>
          {/* Sphere, not a ring -- rotation-invariant, so the "selected" glow
              reads correctly from every camera angle without billboarding. */}
          <sphereGeometry args={[coreRadius * 1.7, 16, 16]} />
          <meshBasicMaterial color={color} transparent opacity={0.35} depthWrite={false} />
        </mesh>
      )}
      <mesh ref={haloRef}>
        <sphereGeometry args={[0.014, 12, 12]} />
        <meshBasicMaterial color={color} transparent opacity={0.5} depthWrite={false} />
      </mesh>
    </group>
  );
}

function CenterTracker({
  onCenterChange,
  active,
}: {
  onCenterChange?: (c: { lat: number; lon: number }) => void;
  active: boolean;
}) {
  const { camera } = useThree();
  const lastReport = useRef(0);

  useFrame(({ clock }) => {
    if (!onCenterChange || !active) return;
    const t = clock.getElapsedTime();
    if (t - lastReport.current < 0.12) return;
    lastReport.current = t;
    onCenterChange(vector3ToLatLon(camera.position));
  });

  return null;
}

/** Drives the camera + morph animation over a fixed duration whenever
 * `transitionRef` holds a pending transition -- deterministic and always
 * reversible, rather than a damped lerp that can drift or never quite
 * settle. */
function TransitionDriver({
  transitionRef,
  morphUniform,
  controlsRef,
  onDone,
}: {
  transitionRef: React.MutableRefObject<Transition | null>;
  morphUniform: { value: number };
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  controlsRef: React.MutableRefObject<any>;
  onDone: () => void;
}) {
  useFrame(() => {
    const t = transitionRef.current;
    if (!t) return;
    const elapsed = (performance.now() - t.startTime) / 1000;
    const progress = Math.min(1, elapsed / EXPAND_DURATION);
    const eased = easeInOutCubic(progress);
    morphUniform.value = THREE.MathUtils.lerp(t.fromMorph, t.toMorph, eased);
    const controls = controlsRef.current;
    if (controls) {
      controls.object.position.lerpVectors(t.fromCamPos, t.toCamPos, eased);
      controls.target.lerpVectors(t.fromTarget, t.toTarget, eased);
      controls.update();
    }
    if (progress >= 1) {
      transitionRef.current = null;
      onDone();
    }
  });
  return null;
}

export function Globe({
  focus,
  markers = [],
  regionBBox,
  className,
  onCenterChange,
  onMarkerClick,
  selectedId,
  enableFlatten = true,
}: GlobeProps) {
  const { theme } = useTheme();
  const [initialCameraPosition] = useState(() => latLonToVector3(focus.lat, focus.lon, CAMERA_DISTANCE));
  const [expanded, setExpanded] = useState(false);
  const [animating, setAnimating] = useState(false);
  const morphUniform = useMemo(() => ({ value: 0 }), []);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const controlsRef = useRef<any>(null);
  const transitionRef = useRef<Transition | null>(null);
  const preExpandCamera = useRef<{ pos: THREE.Vector3; target: THREE.Vector3 } | null>(null);

  const bboxFlatCenter = useMemo(() => {
    if (!regionBBox) return new THREE.Vector3(0, 0, 0);
    return latLonToFlatVector3(
      (regionBBox.latMin + regionBBox.latMax) / 2,
      (regionBBox.lonMin + regionBBox.lonMax) / 2,
    );
  }, [regionBBox]);

  const toggleExpand = useCallback(() => {
    const controls = controlsRef.current;
    if (!controls) return;
    const camera = controls.object as THREE.PerspectiveCamera;
    const next = !expanded;

    if (next) {
      preExpandCamera.current = { pos: camera.position.clone(), target: (controls.target as THREE.Vector3).clone() };
    }

    // Deliberately not a straight top-down shot: looking exactly down the
    // same axis the depth stems extrude along would foreshorten every stem
    // to an invisible dot, silently throwing away the one thing a flat map
    // can't otherwise show. An oblique angle keeps depth legible as a real
    // 3D cue on the "flat" map too.
    const toCamPos = next
      ? bboxFlatCenter.clone().add(new THREE.Vector3(0, -0.55, 0.78))
      : (preExpandCamera.current?.pos.clone() ?? initialCameraPosition.clone());
    const toTarget = next ? bboxFlatCenter.clone() : new THREE.Vector3(0, 0, 0);

    transitionRef.current = {
      startTime: performance.now(),
      fromMorph: morphUniform.value,
      toMorph: next ? 1 : 0,
      fromCamPos: camera.position.clone(),
      toCamPos,
      fromTarget: (controls.target as THREE.Vector3).clone(),
      toTarget,
    };
    setExpanded(next);
    setAnimating(true);
  }, [expanded, bboxFlatCenter, initialCameraPosition, morphUniform]);

  const handleSurfaceClick = useCallback(
    (e: ThreeEvent<MouseEvent>) => {
      e.stopPropagation();
      if (!enableFlatten || animating) return;
      toggleExpand();
    },
    [enableFlatten, animating, toggleExpand],
  );

  return (
    <div className={className} style={{ position: "relative", aspectRatio: "1 / 1", cursor: expanded ? "default" : "grab" }}>
      <Canvas camera={{ position: initialCameraPosition.toArray(), fov: 42 }} dpr={[1, 1.5]} performance={{ min: 0.5 }}>
        <Suspense fallback={null}>
          {theme === "dark" && (
            <>
              <color attach="background" args={["#000000"]} />
              <Stars radius={80} depth={40} count={1200} factor={2} saturation={0} fade />
            </>
          )}
          <ambientLight intensity={theme === "dark" ? 1.15 : 1.6} />
          <directionalLight position={[5, 2, 5]} intensity={1.6} />
          <EarthMesh morphUniform={morphUniform} onSurfaceClick={handleSurfaceClick} />
          {regionBBox && <RegionOutline regionBBox={regionBBox} morphUniform={morphUniform} />}
          {markers.map((marker) => (
            <Marker
              key={marker.id}
              marker={marker}
              selected={marker.id === selectedId}
              onClick={onMarkerClick}
              morphUniform={morphUniform}
            />
          ))}
          <CenterTracker onCenterChange={onCenterChange} active={!expanded && !animating} />
          <TransitionDriver
            transitionRef={transitionRef}
            morphUniform={morphUniform}
            controlsRef={controlsRef}
            onDone={() => setAnimating(false)}
          />
          <OrbitControls
            ref={controlsRef}
            target={[0, 0, 0]}
            enabled={!animating}
            enableZoom={expanded}
            enablePan={expanded}
            enableRotate={!expanded}
            autoRotate={!selectedId && !expanded && !animating}
            autoRotateSpeed={0.35}
            enableDamping
            dampingFactor={0.08}
            rotateSpeed={0.55}
            minPolarAngle={Math.PI * 0.08}
            maxPolarAngle={Math.PI * 0.92}
          />
        </Suspense>
      </Canvas>
      {regionBBox && enableFlatten && (
        <button
          onClick={toggleExpand}
          disabled={animating}
          className="font-nav absolute bottom-3 right-3 rounded-full border px-3 py-1.5 text-[11px] backdrop-blur"
          style={{ borderColor: "var(--color-border)", backgroundColor: "var(--color-bg)", opacity: animating ? 0.5 : 0.9 }}
        >
          {expanded ? "↩ Back to globe" : "⤢ Unwrap to flat map"}
        </button>
      )}
    </div>
  );
}
