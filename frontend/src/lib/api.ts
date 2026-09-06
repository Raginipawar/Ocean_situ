import { API_BASE_URL } from "./config";
import type { FusedResponse, HealthResponse, ModelSnapshot, ObservationSnapshot } from "./types";

export class ApiError extends Error {
  status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function getJson<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`);
  } catch {
    throw new ApiError(
      `Could not reach the Graph Fusion Engine at ${API_BASE_URL}${path}. Is \`uvicorn graph_fusion.api:app --port 8000\` running?`,
    );
  }
  if (!res.ok) {
    throw new ApiError(`${path} responded with ${res.status}`, res.status);
  }
  return res.json() as Promise<T>;
}

// Real endpoints exposed by varuna-graph-fusion/src/graph_fusion/api.py.
// There is no client-side mock fallback here on purpose — if the backend
// isn't running, the UI should say so, not silently fabricate ocean data.
export const api = {
  health: () => getJson<HealthResponse>("/health"),
  model: () => getJson<ModelSnapshot>("/model"),
  observations: () => getJson<ObservationSnapshot>("/observations"),
  fused: (engine: "auto" | "gnn" | "fallback" = "auto") =>
    getJson<FusedResponse>(`/fused?engine=${engine}`),
};
