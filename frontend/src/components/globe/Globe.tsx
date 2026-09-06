import { OrbitControls, Line, Stars, useTexture } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import earthDayMap from "../../assets/textures/earth_daymap.jpg";
import earthNightMap from "../../assets/textures/earth_nightmap.jpg";
import earthCloudsMap from "../../assets/textures/earth_clouds.jpg";
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
  /** Geographic point the camera starts facing. */
  focus: { lat: number; lon: number };
  markers?: GlobeMarker[];
  /** Draws the real scope-lock bounding box from lib/config.ts as a highlighted outline. */
  regionBBox?: RegionBBox;
  className?: string;
  onCenterChange?: (center: { lat: number; lon: number }) => void;
}

const EARTH_RADIUS = 1;
const CAMERA_DISTANCE = 3.1;

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

function EarthMesh() {
  const [dayMap, nightMap, cloudsMap] = useTexture([earthDayMap, earthNightMap, earthCloudsMap]);

  useEffect(() => {
    [dayMap, nightMap, cloudsMap].forEach((tex) => {
      tex.colorSpace = THREE.SRGBColorSpace;
      tex.anisotropy = 4;
    });
  }, [dayMap, nightMap, cloudsMap]);

  const cloudsRef = useRef<THREE.Mesh>(null);

  useFrame((_, delta) => {
    if (cloudsRef.current) cloudsRef.current.rotation.y += delta * 0.018;
  });

  return (
    <>
      <mesh>
        <sphereGeometry args={[EARTH_RADIUS, 64, 64]} />
        <meshStandardMaterial
          map={dayMap}
          emissiveMap={nightMap}
          emissive="#ffe9b3"
          emissiveIntensity={0.35}
          roughness={0.85}
          metalness={0}
        />
      </mesh>
      <mesh ref={cloudsRef}>
        <sphereGeometry args={[EARTH_RADIUS * 1.008, 64, 64]} />
        <meshStandardMaterial map={cloudsMap} transparent opacity={0.35} depthWrite={false} />
      </mesh>
      <mesh>
        <sphereGeometry args={[EARTH_RADIUS * 1.05, 32, 32]} />
        <shaderMaterial
          side={THREE.BackSide}
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
          uniforms={{ glowColor: { value: new THREE.Color("#79a4c0") } }}
          vertexShader={`
            varying float intensity;
            void main() {
              vec3 viewDir = normalize(cameraPosition - (modelMatrix * vec4(position, 1.0)).xyz);
              vec3 worldNormal = normalize(mat3(modelMatrix) * normal);
              intensity = pow(0.62 - dot(worldNormal, viewDir), 3.2);
              gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
            }
          `}
          fragmentShader={`
            varying float intensity;
            uniform vec3 glowColor;
            void main() {
              gl_FragColor = vec4(glowColor, clamp(intensity, 0.0, 1.0));
            }
          `}
        />
      </mesh>
    </>
  );
}

function Marker({ marker }: { marker: GlobeMarker }) {
  const haloRef = useRef<THREE.Mesh>(null);
  const position = useMemo(
    () => latLonToVector3(marker.lat, marker.lon, EARTH_RADIUS * 1.015),
    [marker.lat, marker.lon],
  );
  const color = marker.color ?? "#79a4c0";

  useFrame(({ clock }) => {
    if (!haloRef.current) return;
    const t = (clock.getElapsedTime() * 0.9) % 1;
    haloRef.current.scale.setScalar(1 + t * 2.2);
    (haloRef.current.material as THREE.MeshBasicMaterial).opacity = 0.5 * (1 - t);
  });

  return (
    <group position={position}>
      <mesh>
        <sphereGeometry args={[0.014, 12, 12]} />
        <meshBasicMaterial color={color} />
      </mesh>
      <mesh ref={haloRef}>
        <sphereGeometry args={[0.014, 12, 12]} />
        <meshBasicMaterial color={color} transparent opacity={0.5} depthWrite={false} />
      </mesh>
    </group>
  );
}

function CenterTracker({ onCenterChange }: { onCenterChange?: (c: { lat: number; lon: number }) => void }) {
  const { camera } = useThree();
  const lastReport = useRef(0);

  useFrame(({ clock }) => {
    if (!onCenterChange) return;
    const t = clock.getElapsedTime();
    if (t - lastReport.current < 0.12) return;
    lastReport.current = t;
    onCenterChange(vector3ToLatLon(camera.position));
  });

  return null;
}

export function Globe({ focus, markers = [], regionBBox, className, onCenterChange }: GlobeProps) {
  const { theme } = useTheme();
  const [initialCameraPosition] = useState(() => latLonToVector3(focus.lat, focus.lon, CAMERA_DISTANCE));
  const bboxPoints = useMemo(
    () => (regionBBox ? bboxRingPoints(regionBBox, EARTH_RADIUS * 1.006) : null),
    [regionBBox],
  );

  return (
    <div className={className} style={{ aspectRatio: "1 / 1", cursor: "grab" }}>
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
          <EarthMesh />
          {bboxPoints && <Line points={bboxPoints} color="#79a4c0" lineWidth={1.6} />}
          {markers.map((marker) => (
            <Marker key={`${marker.label}-${marker.lat}-${marker.lon}`} marker={marker} />
          ))}
          <CenterTracker onCenterChange={onCenterChange} />
          <OrbitControls
            target={[0, 0, 0]}
            enableZoom={false}
            enablePan={false}
            autoRotate
            autoRotateSpeed={0.35}
            enableDamping
            dampingFactor={0.08}
            rotateSpeed={0.55}
            minPolarAngle={Math.PI * 0.08}
            maxPolarAngle={Math.PI * 0.92}
          />
        </Suspense>
      </Canvas>
    </div>
  );
}
