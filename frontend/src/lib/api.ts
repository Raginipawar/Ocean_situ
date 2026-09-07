import { API_BASE_URL, DRIFT_API_BASE_URL } from "./config";
import type { Alert, FusedResponse, HealthResponse, ModelSnapshot, ObservationSnapshot } from "./types";

export class ApiError extends Error {
  status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function getJsonFrom<T>(base: string, path: string, unreachableHint: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${base}${path}`);
  } catch {
    throw new ApiError(`Could not reach ${base}${path}. ${unreachableHint}`);
  }
  if (!res.ok) {
    throw new ApiError(`${path} responded with ${res.status}`, res.status);
  }
  return res.json() as Promise<T>;
}

async function getJson<T>(path: string): Promise<T> {
  return getJsonFrom<T>(API_BASE_URL, path, "Is `uvicorn graph_fusion.api:app --port 8000` running?");
}

// Real endpoints exposed by varuna-graph-fusion/src/graph_fusion/api.py.
// There is no client-side mock fallback here on purpose. If the backend
// isn't running, the UI should say so, not silently fabricate ocean data.
export const api = {
  health: () => getJson<HealthResponse>("/health"),
  model: () => getJson<ModelSnapshot>("/model"),
  observations: () => getJson<ObservationSnapshot>("/observations"),
  fused: (engine: "auto" | "gnn" | "fallback" = "auto") =>
    getJson<FusedResponse>(`/fused?engine=${engine}`),
};

// Person 2's Drift Memory Engine (drift-memory-engine/) -- a separate
// FastAPI process. Same "no fabricated fallback" rule: if it isn't running,
// the alert panel says so instead of inventing alerts.
//
// use_upstream=true asks it to fetch our own live /fused output (real GNN
// corrections against Person 6's real sensors) and compute alerts from
// that, instead of its built-in demo scenario. It already falls back to the
// scenario internally if our engine is unreachable, so this is strictly a
// "prefer real, degrade gracefully" upgrade -- not a new failure mode.
export const driftApi = {
  alerts: () =>
    getJsonFrom<Alert[]>(
      DRIFT_API_BASE_URL,
      "/alerts?use_upstream=true",
      "Is `uvicorn drift_memory.api:app --port 8002` running from drift-memory-engine/?",
    ),
};
