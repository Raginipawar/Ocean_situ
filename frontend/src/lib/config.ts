/**
 * Mirrors the scope-lock in varuna-graph-fusion/src/graph_fusion/config.py.
 * Kept in one place so the globe's default focus, the region label, and the
 * trust-overlay thresholds shown in the UI never drift from what the backend
 * actually computes.
 */

export const REGION_NAME = "bay_of_bengal";
export const REGION_LABEL = "Bay of Bengal";

export const REGION_BBOX = {
  latMin: 5.0,
  latMax: 22.0,
  lonMin: 80.0,
  lonMax: 100.0,
};

export const REGION_CENTER = {
  lat: (REGION_BBOX.latMin + REGION_BBOX.latMax) / 2,
  lon: (REGION_BBOX.lonMin + REGION_BBOX.lonMax) / 2,
};

export const VARIABLES = ["sst_c", "current_u_ms", "current_v_ms", "wave_height_m"] as const;

// TRUST_GREEN_MIN / TRUST_AMBER_MIN from config.py — confidence >= green is
// "green", >= amber is "amber", below that is "red". The backend computes
// trust_label itself; these are only for rendering a legend, never for
// re-deriving a label client-side.
export const TRUST_GREEN_MIN = 0.7;
export const TRUST_AMBER_MIN = 0.4;

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
