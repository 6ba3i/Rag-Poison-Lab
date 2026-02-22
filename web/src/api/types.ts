export type RecommendationMode = "baseline" | "attacked";
export type HistorySplit = "train" | "all";
export type ProviderName = "local" | "chatgpt" | "claude" | "gemini" | "qwen";
export type RankingMode = "deterministic" | "llm_rerank";

export interface UserSummary {
  user_id: number;
  rating_count: number;
  mean_rating: number;
}

export interface TopGenre {
  genre: string;
  count: number;
}

export interface UserProfile {
  user_id: number;
  rating_count: number;
  mean_rating: number;
  top_genres: TopGenre[];
  top_rated_movie_ids: number[];
  recent_movie_ids: number[];
}

export interface UserHistoryItem {
  movie_id: number;
  title: string;
  rating: number;
  timestamp: number;
  genres: string[];
  split: "train" | "test" | null;
}

export interface RecommendationItem {
  movie_id: number;
  title: string;
  genres: string[];
  score: number;
  explanation: string;
}

export interface TraceDoc {
  movie_id: number;
  title: string;
  snippet: string;
  poison_marker: boolean;
  poison_payload: string;
  has_poison: boolean;
}

export interface TraceResponse {
  user_id: number;
  mode: RecommendationMode;
  ranking_mode: RankingMode;
  retrieval_query: string;
  retrieved_docs: TraceDoc[];
  rerank_candidates?: TraceRerankCandidate[] | null;
  rerank_prompt?: string | null;
  rerank_raw_response?: string | null;
  rerank_parsed_order?: number[] | null;
  rerank_fallback?: boolean | null;
}

export interface TraceRerankCandidate {
  index: number;
  movie_id: number;
  title: string;
  genres: string[];
  year?: number | null;
}

export interface LlmRoleConfig {
  provider: ProviderName;
  model: string;
}

export interface LlmConfig {
  victim: LlmRoleConfig;
  attacker: LlmRoleConfig;
  ranking_mode: RankingMode;
}

export interface LlmProviderOption {
  provider: ProviderName;
  available: boolean;
  models: string[];
}

export interface LlmSettingsOptionsResponse {
  providers: LlmProviderOption[];
}
