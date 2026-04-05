import {
  type AttackSettingsResponse,
  type ExperimentRunRequest,
  type ExperimentRunResponse,
  type HistorySplit,
  type LlmConfig,
  type LlmSettingsOptionsResponse,
  type RecommendationItem,
  type RecommendationMode,
  type RunDetailResponse,
  type RunsListResponse,
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

export type ExperimentRunStreamEvent =
  | { type: "log"; line: string }
  | { type: "complete"; summary: ExperimentRunResponse }
  | { type: "failed"; detail: string; statusCode: number };

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

export async function runExperimentStream(
  payload: ExperimentRunRequest,
  onEvent: (event: ExperimentRunStreamEvent) => void,
  signal?: AbortSignal,
): Promise<ExperimentRunResponse> {
  const response = await fetch(`${API_BASE}/experiments/run/stream`, {
    method: "POST",
    signal,
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const contentType = response.headers.get("content-type") ?? "";
    const isJson = contentType.includes("application/json");
    const payloadValue = isJson ? await response.json() : await response.text();
    const detail =
      typeof payloadValue === "object" && payloadValue !== null && "detail" in payloadValue
        ? String((payloadValue as { detail: unknown }).detail)
        : response.statusText || "Request failed";
    throw new ApiError(response.status, detail);
  }

  if (!response.body) {
    throw new ApiError(500, "Experiment stream body is unavailable.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let completedSummary: ExperimentRunResponse | null = null;

  while (true) {
    const chunk = await reader.read();
    if (chunk.done) {
      break;
    }

    buffer += decoder.decode(chunk.value, { stream: true }).replace(/\r\n/g, "\n");
    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      boundary = buffer.indexOf("\n\n");

      const parsed = parseSseFrame(frame);
      if (!parsed) {
        continue;
      }

      if (parsed.event === "log") {
        const line = extractStringField(parsed.data, "line");
        if (line !== null) {
          onEvent({ type: "log", line });
        }
        continue;
      }

      if (parsed.event === "failed") {
        const detail = extractStringField(parsed.data, "detail") ?? "Experiment run failed";
        const statusCode = extractNumberField(parsed.data, "status_code") ?? 500;
        onEvent({ type: "failed", detail, statusCode });
        throw new ApiError(statusCode, detail);
      }

      if (parsed.event === "complete") {
        const summary = extractSummaryField(parsed.data, "summary");
        if (summary !== null) {
          completedSummary = summary;
          onEvent({ type: "complete", summary });
        }
      }
    }
  }

  if (completedSummary !== null) {
    return completedSummary;
  }
  throw new ApiError(500, "Experiment stream ended before completion.");
}

export function getAttackSettings(): Promise<AttackSettingsResponse> {
  return apiRequest<AttackSettingsResponse>("/settings/attack");
}

export function listResultRuns(limit = 20, cursor: string | null = null): Promise<RunsListResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (cursor) {
    params.set("cursor", cursor);
  }
  return apiRequest<RunsListResponse>(`/results/runs?${params.toString()}`);
}

export function getResultRunDetail(label: string): Promise<RunDetailResponse> {
  return apiRequest<RunDetailResponse>(`/results/runs/${encodeURIComponent(label)}`);
}

function parseSseFrame(frame: string): { event: string; data: unknown } | null {
  const lines = frame.split("\n");
  let event = "message";
  const dataLines: string[] = [];

  for (const line of lines) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
      continue;
    }
    if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  }

  if (dataLines.length === 0) {
    return null;
  }

  try {
    return { event, data: JSON.parse(dataLines.join("\n")) };
  } catch {
    return null;
  }
}

function extractStringField(value: unknown, field: string): string | null {
  if (!isRecord(value) || typeof value[field] !== "string") {
    return null;
  }
  return value[field];
}

function extractNumberField(value: unknown, field: string): number | null {
  if (!isRecord(value) || typeof value[field] !== "number") {
    return null;
  }
  return value[field];
}

function extractSummaryField(value: unknown, field: string): ExperimentRunResponse | null {
  if (!isRecord(value) || !isRecord(value[field])) {
    return null;
  }
  return value[field] as ExperimentRunResponse;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
