from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from common.schemas.attack_config import AttackType, TargetBoostField, TargetBoostPolicy
from common.schemas.defense_config import DefenseSuspicionMode
from common.schemas.llm_config import LlmConfig, ProviderName, RankingMode, RetrievalMode

RecommendationMode = Literal["baseline", "attacked"]
HistorySplit = Literal["train", "all"]


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    elasticsearch_connected: bool
    ollama_connected: bool


class UserSummary(BaseModel):
    user_id: int
    rating_count: int
    mean_rating: float


class TopGenre(BaseModel):
    genre: str
    count: int


class UserProfile(BaseModel):
    user_id: int
    rating_count: int
    mean_rating: float
    top_genres: list[TopGenre]
    top_rated_movie_ids: list[int]
    recent_movie_ids: list[int]


class UserHistoryItem(BaseModel):
    movie_id: int
    title: str
    rating: float
    timestamp: int
    genres: list[str]
    split: Literal["train", "test"] | None = None


class RecommendationsRequest(BaseModel):
    user_id: int = Field(ge=1)
    mode: RecommendationMode = "baseline"
    k: int = Field(default=10, ge=1, le=100)


class RecommendationItem(BaseModel):
    movie_id: int
    title: str
    genres: list[str]
    score: float
    explanation: str


class TraceRequest(BaseModel):
    user_id: int = Field(ge=1)
    mode: RecommendationMode = "baseline"
    k_retrieval: int = Field(default=20, ge=1, le=200)


class TraceDoc(BaseModel):
    movie_id: int
    title: str
    snippet: str
    poison_marker: bool = False
    poison_payload: str = ""
    has_poison: bool = False


class TraceRerankCandidate(BaseModel):
    index: int = Field(ge=1)
    movie_id: int
    title: str
    genres: list[str]
    year: int | None = None


class TraceResponse(BaseModel):
    user_id: int
    mode: RecommendationMode
    ranking_mode: RankingMode = "deterministic"
    effective_ranking_mode: RankingMode | None = None
    retrieval_mode: RetrievalMode = "lexical"
    retrieval_query: str
    retrieved_docs: list[TraceDoc]
    rerank_attempted: bool | None = None
    rerank_candidates: list[TraceRerankCandidate] | None = None
    rerank_prompt: str | None = None
    rerank_raw_response: str | None = None
    rerank_parsed_order: list[int] | None = None
    rerank_fallback: bool | None = None
    rerank_fallback_reason: str | None = None
    rerank_response_model: str | None = None
    rerank_error: str | None = None
    rerank_provider: ProviderName | None = None
    rerank_model: str | None = None
    rerank_base_url: str | None = None
    rerank_base_url_source: str | None = None
    rerank_uses_victim_only: bool = False
    attacker_provider: ProviderName | None = None
    attacker_model: str | None = None
    retrieval_debug: dict[str, Any] | None = None


class LlmProviderOption(BaseModel):
    provider: ProviderName
    available: bool
    models: list[str]


class LlmSettingsOptionsResponse(BaseModel):
    providers: list[LlmProviderOption]


class LlmSettingsResponse(BaseModel):
    config: LlmConfig


class ExperimentRunRequest(BaseModel):
    label: str | None = None
    mode: Literal["single", "batch", "full"] = "single"
    run_profile: Literal["pipeline", "single_demo"] = "pipeline"
    k: int = Field(default=10, ge=1, le=100)
    user_id: int | None = Field(default=None, ge=1)
    batch_size: int = Field(default=100, ge=1)
    run_prepare: bool | None = None
    run_index: bool | None = None
    run_eval: bool | None = None
    run_report: bool | None = None
    overwrite: bool = False
    dataset_dir: str | None = None
    output_dir: str | None = None
    es_url: str | None = None
    attack_config: str | None = None
    repeat_count: int = Field(default=1, ge=1, le=100)
    seed: int = Field(default=42, ge=0)


class ExperimentRunResponse(BaseModel):
    label: str | None = None
    prepare: dict[str, Any] | None = None
    index: dict[str, Any] | None = None
    eval: dict[str, Any] | None = None
    report: dict[str, Any] | None = None
    run_dir: str | None = None


class AttackSettingsResponse(BaseModel):
    attack_type: AttackType
    poison_fraction: float
    target_movie_id: int | None = None
    payload_text: str
    keyword_list: list[str]
    target_boost_policy: TargetBoostPolicy
    target_boost_strength: int
    target_fields: list[TargetBoostField]
    config_path: str
    config_exists: bool
    config_sha256: str | None = None


class AttackSettingsRequest(BaseModel):
    attack_type: AttackType
    poison_fraction: float = Field(ge=0.0, le=1.0)
    target_movie_id: int | None = Field(default=None, ge=1)
    payload_text: str = ""
    keyword_list: list[str] = Field(default_factory=list)
    target_boost_policy: TargetBoostPolicy = "keyword_burst"
    target_boost_strength: int = Field(default=4, ge=1, le=20)
    target_fields: list[TargetBoostField] = Field(default_factory=list)


class DefenseSettingsRequest(BaseModel):
    enabled: bool = False
    retrieval_guard_enabled: bool = True
    retrieval_suspicion_mode: DefenseSuspicionMode = "filter"
    retrieval_penalty_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    rerank_sanitization_enabled: bool = True
    suspicious_patterns: list[str] = Field(default_factory=list)


class DefenseSettingsResponse(BaseModel):
    enabled: bool = False
    retrieval_guard_enabled: bool = True
    retrieval_suspicion_mode: DefenseSuspicionMode = "filter"
    retrieval_penalty_weight: float = 0.5
    rerank_sanitization_enabled: bool = True
    suspicious_patterns: list[str] = Field(default_factory=list)
    config_path: str
    config_exists: bool
    config_sha256: str | None = None


class MetricStats(BaseModel):
    count: int = 0
    mean: float = 0.0
    stddev: float = 0.0
    stderr: float = 0.0
    ci95_low: float | None = None
    ci95_high: float | None = None


class MetricComparisonSignificance(BaseModel):
    count: int = 0
    positive: int = 0
    negative: int = 0
    ties: int = 0
    p_value: float | None = None
    method: str = "paired_sign_test"
    direction: str | None = None


class RepeatStatsSection(BaseModel):
    metrics: dict[str, MetricStats] = Field(default_factory=dict)
    significance: dict[str, MetricComparisonSignificance] = Field(default_factory=dict)


class RepeatStatsResponse(BaseModel):
    repeat_count: int = 0
    seed: int = 42
    baseline: RepeatStatsSection | None = None
    attacked: RepeatStatsSection | None = None
    delta: RepeatStatsSection | None = None
    defended: RepeatStatsSection | None = None
    defense_delta: RepeatStatsSection | None = None


class RunSummary(BaseModel):
    label: str
    generated_at_utc: str | None = None
    mode: str | None = None
    k: int | None = None
    requested_users: int | None = None
    evaluated_users: int | None = None
    skipped_users: int | None = None
    target_movie_id: int | None = None
    baseline: dict[str, float] = Field(default_factory=dict)
    attacked: dict[str, float] = Field(default_factory=dict)
    delta: dict[str, float] = Field(default_factory=dict)
    defended: dict[str, float] = Field(default_factory=dict)
    defense_delta: dict[str, float] = Field(default_factory=dict)
    warnings_count: int = 0
    repeat_count: int = 1
    has_metrics: bool = False
    has_manifest: bool = False
    has_attack_trace: bool = False
    has_summary: bool = False
    has_delta_csv: bool = False


class RunsListResponse(BaseModel):
    items: list[RunSummary] = Field(default_factory=list)
    next_cursor: str | None = None
    total: int = 0


class RunArtifacts(BaseModel):
    run_dir: str
    metrics_path: str | None = None
    manifest_path: str | None = None
    attack_trace_path: str | None = None
    summary_path: str | None = None
    delta_csv_path: str | None = None
    llm_runtime_path: str | None = None
    attack_runtime_path: str | None = None
    defense_runtime_path: str | None = None
    llm_snapshot_path: str | None = None
    attack_snapshot_path: str | None = None
    defense_snapshot_path: str | None = None


class RunDetailResponse(BaseModel):
    summary: RunSummary
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] | None = None
    target_retrieval: dict[str, Any] | None = None
    repeat_stats: RepeatStatsResponse | None = None
    per_user: list[dict[str, Any]] = Field(default_factory=list)
    manifest: dict[str, Any] | None = None
    artifacts: RunArtifacts
