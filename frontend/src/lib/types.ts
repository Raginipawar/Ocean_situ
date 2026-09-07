/**
 * Mirrors varuna-graph-fusion/src/graph_fusion/schemas.py exactly.
 * If the backend contract changes, update this file only. Every component
 * that talks to the API imports these types instead of redefining shapes.
 */

export type SensorType =
  | "argo"
  | "glider"
  | "ctd"
  | "buoy"
  | "mooring"
  | "hf_radar"
  | "adcp"
  | "drifter"
  | "xbt";

export interface GeoPoint {
  lat: number;
  lon: number;
  depth_m: number;
}

export interface ModelGridPoint extends GeoPoint {
  sst_c: number | null;
  current_u_ms: number | null;
  current_v_ms: number | null;
  wave_height_m: number | null;
}

export interface ModelSnapshot {
  region: string;
  time: string;
  resolution_deg: number;
  source: string;
  points: ModelGridPoint[];
}

export interface ObservationPoint extends GeoPoint {
  sensor_id: string;
  sensor_type: SensorType;
  time: string;
  sst_c: number | null;
  current_u_ms: number | null;
  current_v_ms: number | null;
  wave_height_m: number | null;
}

export interface ObservationSnapshot {
  region: string;
  time: string;
  source: string;
  points: ObservationPoint[];
}

export type TrustLabel = "green" | "amber" | "red";

export interface FusedPoint extends GeoPoint {
  sst_c: number | null;
  current_u_ms: number | null;
  current_v_ms: number | null;
  wave_height_m: number | null;
  correction_sst_c: number | null;
  correction_current_u_ms: number | null;
  correction_current_v_ms: number | null;
  correction_wave_height_m: number | null;
  confidence: number;
  trust_label: TrustLabel;
  is_sensor_node: boolean;
  support: number;
}

export interface FusionSummary {
  engine: "gnn" | "fallback";
  n_sensors: number;
  n_grid_points: number;
  n_graph_edges: number;
  mean_confidence: number;
  mean_abs_correction_sst_c: number | null;
  validation_mae_sst_c: number | null;
  runtime_ms: number;
}

export interface FusedResponse {
  region: string;
  time: string;
  points: FusedPoint[];
  summary: FusionSummary;
}

export interface HealthResponse {
  status: string;
  region: string;
}

/** Mirrors drift-memory-engine/src/drift_memory/schemas.py::Alert (Person 2's contract). */
export type AlertSeverity = "info" | "warning" | "critical";

export interface Alert {
  id: string;
  region: string;
  variable: string;
  severity: AlertSeverity;
  message: string;
  timestamp: string;
  lat: number;
  lon: number;
  model_value: number;
  observed_value: number;
  divergence: number;
}

/** Mirrors graph_fusion/schemas.py::DepthLevel / DepthProfile / DepthProfileSnapshot.
 * Real Argo/glider/CTD casts carry multiple levels; surface-only instruments
 * (buoys, moorings, drifters) carry exactly one real level -- never a
 * fabricated deeper one. */
export interface DepthLevel {
  depth_m: number;
  sst_c: number | null;
  salinity_psu: number | null;
  current_u_ms: number | null;
  current_v_ms: number | null;
  chlorophyll_mg_m3: number | null;
}

export interface DepthProfile {
  sensor_id: string;
  sensor_type: SensorType;
  lat: number;
  lon: number;
  time: string;
  levels: DepthLevel[];
}

export interface DepthProfileSnapshot {
  region: string;
  time: string;
  source: string;
  profiles: DepthProfile[];
}

/** Mirrors graph_fusion/schemas.py::NowcastInfo (Person 3's real, verified
 * training results -- not live per-click inference). */
export interface NowcastInfo {
  available: boolean;
  architecture: string | null;
  n_parameters: number | null;
  trained_on: string | null;
  variables: string[];
  depth_levels: number | null;
  held_out_test_mse: number | null;
  persistence_baseline_mse: number | null;
  improvement_over_baseline_pct: number | null;
  sst_mae_c: number | null;
  note: string;
}

/** Mirrors graph_fusion/schemas.py::VolumetricMeta / VolumetricSnapshot /
 * VolumetricCellSeries -- the real, dense Copernicus-derived grid (Person
 * 3's export) backing the 3D Cube Explorer's free-roam navigation. */
export interface VolumetricMeta {
  region: string;
  lat: number[];
  lon: number[];
  depth_m: number[];
  time: string[];
  variables: string[];
  source: string;
}

/** [depth][lat][lon] nested arrays, one real day, every variable. */
export interface VolumetricSnapshot {
  time: string;
  depth_m: number[];
  lat: number[];
  lon: number[];
  sst_c: number[][][];
  salinity_psu: number[][][];
  current_u_ms: number[][][];
  current_v_ms: number[][][];
  wave_height_m: number[][][];
  chlorophyll_mg_m3: number[][][];
}

/** [time][depth] nested arrays, one real grid cell, the full real time series. */
export interface VolumetricCellSeries {
  lat: number;
  lon: number;
  depth_m: number[];
  time: string[];
  sst_c: number[][];
  salinity_psu: number[][];
  current_u_ms: number[][];
  current_v_ms: number[][];
  wave_height_m: number[][];
  chlorophyll_mg_m3: number[][];
}
