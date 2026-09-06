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
