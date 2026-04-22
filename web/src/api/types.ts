export type RecommendationMode = "baseline" | "attacked";
export type HistorySplit = "train" | "all";
export type ProviderName = "local" | "chatgpt" | "claude" | "gemini" | "qwen";
export type RankingMode = "deterministic" | "llm_rerank";
export type RetrievalMode = "lexical" | "dense" | "hybrid";
export type DefenseSuspicionMode = "filter" | "penalize";

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
  effective_ranking_mode?: RankingMode | null;
  retrieval_mode: RetrievalMode;
  retrieval_query: string;
  retrieved_docs: TraceDoc[];
  rerank_attempted?: boolean | null;
  rerank_candidates?: TraceRerankCandidate[] | null;
  rerank_prompt?: string | null;
  rerank_raw_response?: string | null;
  rerank_parsed_order?: number[] | null;
  rerank_fallback?: boolean | null;
  rerank_fallback_reason?: string | null;
  retrieval_debug?: Record<string, unknown> | null;
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
  retrieval_mode: RetrievalMode;
}

export interface LlmProviderOption {
  provider: ProviderName;
  available: boolean;
  models: string[];
}

export interface LlmSettingsOptionsResponse {
  providers: LlmProviderOption[];
}

export interface ExperimentRunRequest {
  label?: string | null;
  mode?: "single" | "batch" | "full";
  run_profile?: "pipeline" | "single_demo";
  k?: number;
  user_id?: number | null;
  batch_size?: number;
  run_prepare?: boolean | null;
  run_index?: boolean | null;
  run_eval?: boolean | null;
  run_report?: boolean | null;
  overwrite?: boolean;
  dataset_dir?: string | null;
  output_dir?: string | null;
  es_url?: string | null;
  attack_config?: string | null;
  repeat_count?: number;
  seed?: number;
}

export interface ExperimentRunResponse {
  label?: string | null;
  prepare?: Record<string, unknown> | null;
  index?: Record<string, unknown> | null;
  eval?: Record<string, unknown> | null;
  report?: Record<string, unknown> | null;
  run_dir?: string | null;
}

export type AttackType = "targeted_promotion" | "untargeted_degradation" | "prompt_injection";
export type TargetBoostPolicy = "disabled" | "keyword_burst" | "aggressive";
export type TargetBoostField = "title" | "genres" | "synopsis";

export interface AttackSettingsResponse {
  attack_type: AttackType;
  poison_fraction: number;
  target_movie_id: number | null;
  payload_text: string;
  keyword_list: string[];
  target_boost_policy: TargetBoostPolicy;
  target_boost_strength: number;
  target_fields: TargetBoostField[];
  config_path: string;
  config_exists: boolean;
  config_sha256: string | null;
}

export interface AttackSettingsRequest {
  attack_type: AttackType;
  poison_fraction: number;
  target_movie_id: number | null;
  payload_text: string;
  keyword_list: string[];
  target_boost_policy: TargetBoostPolicy;
  target_boost_strength: number;
  target_fields: TargetBoostField[];
}

export interface DefenseSettingsRequest {
  enabled: boolean;
  retrieval_guard_enabled: boolean;
  retrieval_suspicion_mode: DefenseSuspicionMode;
  retrieval_penalty_weight: number;
  rerank_sanitization_enabled: boolean;
  suspicious_patterns: string[];
}

export interface DefenseSettingsResponse extends DefenseSettingsRequest {
  config_path: string;
  config_exists: boolean;
  config_sha256: string | null;
}

export interface MetricStats {
  count: number;
  mean: number;
  stddev: number;
  stderr: number;
  ci95_low: number | null;
  ci95_high: number | null;
}

export interface MetricComparisonSignificance {
  count: number;
  positive: number;
  negative: number;
  ties: number;
  p_value: number | null;
  method: string;
  direction: string | null;
}

export interface RepeatStatsSection {
  metrics: Record<string, MetricStats>;
  significance: Record<string, MetricComparisonSignificance>;
}

export interface RepeatStatsResponse {
  repeat_count: number;
  seed: number;
  baseline?: RepeatStatsSection | null;
  attacked?: RepeatStatsSection | null;
  delta?: RepeatStatsSection | null;
  defended?: RepeatStatsSection | null;
  defense_delta?: RepeatStatsSection | null;
}

export interface RunSummary {
  label: string;
  generated_at_utc: string | null;
  mode: string | null;
  k: number | null;
  requested_users: number | null;
  evaluated_users: number | null;
  skipped_users: number | null;
  target_movie_id: number | null;
  baseline: Record<string, number>;
  attacked: Record<string, number>;
  delta: Record<string, number>;
  defended: Record<string, number>;
  defense_delta: Record<string, number>;
  warnings_count: number;
  repeat_count: number;
  has_metrics: boolean;
  has_manifest: boolean;
  has_attack_trace: boolean;
  has_summary: boolean;
  has_delta_csv: boolean;
}

export interface RunsListResponse {
  items: RunSummary[];
  next_cursor: string | null;
  total: number;
}

export interface RunArtifacts {
  run_dir: string;
  metrics_path: string | null;
  manifest_path: string | null;
  attack_trace_path: string | null;
  summary_path: string | null;
  delta_csv_path: string | null;
  llm_runtime_path: string | null;
  attack_runtime_path: string | null;
  defense_runtime_path: string | null;
  llm_snapshot_path: string | null;
  attack_snapshot_path: string | null;
  defense_snapshot_path: string | null;
}

export interface RunDetailResponse {
  summary: RunSummary;
  warnings: string[];
  metadata: Record<string, unknown> | null;
  target_retrieval: Record<string, unknown> | null;
  repeat_stats: RepeatStatsResponse | null;
  per_user: Record<string, unknown>[];
  manifest: Record<string, unknown> | null;
  artifacts: RunArtifacts;
}
