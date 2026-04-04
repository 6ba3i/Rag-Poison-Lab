import {
  type ExperimentRunRequest,
  type ExperimentRunResponse,
  type HistorySplit,
  type LlmConfig,
  type LlmSettingsOptionsResponse,
  type RecommendationItem,
  type RecommendationMode,
  type TraceResponse,
  type UserHistoryItem,
  type UserProfile,
  type UserSummary,
} from "./types";

const API_BASE = "/api";

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(`API ${status}: ${detail}`);
    this.status = status;
    this.detail = detail;
  }
}

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  const contentType = response.headers.get("content-type") ?? "";
  const isJson = contentType.includes("application/json");
  const payload = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    const detail =
      typeof payload === "object" && payload !== null && "detail" in payload
        ? String((payload as { detail: unknown }).detail)
        : response.statusText || "Request failed";
    throw new ApiError(response.status, detail);
  }

  return payload as T;
}

export function listUsers(q: string, limit = 50): Promise<UserSummary[]> {
  const params = new URLSearchParams({ q, limit: String(limit) });
  return apiRequest<UserSummary[]>(`/users?${params.toString()}`);
}

export function getUserProfile(userId: number): Promise<UserProfile> {
  return apiRequest<UserProfile>(`/users/${userId}/profile`);
}

export function getUserHistory(userId: number, split: HistorySplit = "all"): Promise<UserHistoryItem[]> {
  const params = new URLSearchParams({ split });
  return apiRequest<UserHistoryItem[]>(`/users/${userId}/history?${params.toString()}`);
}

export function getRecommendations(
  userId: number,
  mode: RecommendationMode,
  k: number,
): Promise<RecommendationItem[]> {
  return apiRequest<RecommendationItem[]>("/recommendations", {
    method: "POST",
    body: JSON.stringify({ user_id: userId, mode, k }),
  });
}

export function getTrace(userId: number, mode: RecommendationMode, kRetrieval: number): Promise<TraceResponse> {
  return apiRequest<TraceResponse>("/trace", {
    method: "POST",
    body: JSON.stringify({ user_id: userId, mode, k_retrieval: kRetrieval }),
  });
}

export function getLlmSettings(): Promise<LlmConfig> {
  return apiRequest<LlmConfig>("/settings/llm");
}

export function saveLlmSettings(config: LlmConfig): Promise<LlmConfig> {
  return apiRequest<LlmConfig>("/settings/llm", {
    method: "PUT",
    body: JSON.stringify(config),
  });
}

export function getLlmOptions(): Promise<LlmSettingsOptionsResponse> {
  return apiRequest<LlmSettingsOptionsResponse>("/settings/llm/options");
}

export function runExperiment(payload: ExperimentRunRequest): Promise<ExperimentRunResponse> {
  return apiRequest<ExperimentRunResponse>("/experiments/run", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
