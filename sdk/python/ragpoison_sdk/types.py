from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

RecommendationMode = Literal["baseline", "attacked"]
HistorySplit = Literal["train", "all"]
ProviderName = Literal["local", "chatgpt", "claude", "gemini", "qwen", "deepseek"]
RankingMode = Literal["deterministic", "llm_rerank"]
RetrievalMode = Literal["lexical", "dense", "hybrid"]
AttackType = Literal["targeted_promotion", "untargeted_degradation", "prompt_injection"]
TargetBoostPolicy = Literal["disabled", "keyword_burst", "aggressive"]
TargetBoostField = Literal["title", "genres", "synopsis"]
DefenseSuspicionMode = Literal["filter", "penalize"]


class SdkBaseModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class UserSummary(SdkBaseModel):
    user_id: int
    rating_count: int
    mean_rating: float


class TopGenre(SdkBaseModel):
    genre: str
    count: int


class UserProfile(SdkBaseModel):
    user_id: int
    rating_count: int
    mean_rating: float
    top_genres: list[TopGenre]
    top_rated_movie_ids: list[int]
    recent_movie_ids: list[int]


class UserHistoryItem(SdkBaseModel):
    movie_id: int
    title: str
    rating: float
    timestamp: int
    genres: list[str]
    split: Literal["train", "test"] | None = None


class RecommendationItem(SdkBaseModel):
    movie_id: int
    title: str
    genres: list[str]
    score: float
    explanation: str


class TraceDoc(SdkBaseModel):
    movie_id: int
    title: str
    snippet: str
    poison_marker: bool = False
    poison_payload: str = ""
    has_poison: bool = False


class TraceRerankCandidate(SdkBaseModel):
    index: int
    movie_id: int
    title: str
    genres: list[str]
    year: int | None = None


class TraceResponse(SdkBaseModel):
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
    retrieval_debug: dict[str, object] | None = None


class LlmRoleConfig(SdkBaseModel):
    provider: ProviderName = "local"
    model: str = Field(min_length=1, max_length=200)

    @field_validator("model")
    @classmethod
    def _normalize_model(cls, value: str) -> str:
        normalized = value.strip()
        if normalized == "":
            raise ValueError("model must not be empty")
        return normalized


class LlmConfig(SdkBaseModel):
    victim: LlmRoleConfig
    attacker: LlmRoleConfig
    ranking_mode: RankingMode = "deterministic"
    retrieval_mode: RetrievalMode = "lexical"


class AttackSettingsRequest(SdkBaseModel):
    attack_type: AttackType
    poison_fraction: float
    target_movie_id: int | None = None
    payload_text: str = ""
    keyword_list: list[str] = Field(default_factory=list)
    target_boost_policy: TargetBoostPolicy = "keyword_burst"
    target_boost_strength: int = 4
    target_fields: list[TargetBoostField] = Field(default_factory=list)


class AttackSettingsResponse(AttackSettingsRequest):
    config_path: str
    config_exists: bool
    config_sha256: str | None = None


class DefenseSettingsRequest(SdkBaseModel):
    enabled: bool = False
    retrieval_guard_enabled: bool = True
    retrieval_suspicion_mode: DefenseSuspicionMode = "filter"
    retrieval_penalty_weight: float = 0.5
    rerank_sanitization_enabled: bool = True
    suspicious_patterns: list[str] = Field(default_factory=list)


class DefenseSettingsResponse(DefenseSettingsRequest):
    config_path: str
    config_exists: bool
    config_sha256: str | None = None


class ExperimentRunRequest(SdkBaseModel):
    label: str | None = None
    mode: Literal["single", "batch", "full"] = "single"
    run_profile: Literal["pipeline", "single_demo"] = "pipeline"
    k: int = 10
    user_id: int | None = None
    batch_size: int = 100
    run_prepare: bool | None = None
    run_index: bool | None = None
    run_eval: bool | None = None
    run_report: bool | None = None
    overwrite: bool = False
    dataset_dir: str | None = None
    output_dir: str | None = None
    es_url: str | None = None
    attack_config: str | None = None
    repeat_count: int = 1
    seed: int = 42


class ExperimentRunResponse(SdkBaseModel):
    label: str | None = None
    prepare: dict[str, object] | None = None
    index: dict[str, object] | None = None
    eval: dict[str, object] | None = None
    report: dict[str, object] | None = None
    run_dir: str | None = None


class MetricStats(SdkBaseModel):
    count: int = 0
    mean: float = 0.0
    stddev: float = 0.0
    stderr: float = 0.0
    ci95_low: float | None = None
    ci95_high: float | None = None


class MetricComparisonSignificance(SdkBaseModel):
    count: int = 0
    positive: int = 0
    negative: int = 0
    ties: int = 0
    p_value: float | None = None
    method: str = "paired_sign_test"
    direction: str | None = None


class RepeatStatsSection(SdkBaseModel):
    metrics: dict[str, MetricStats] = Field(default_factory=dict)
    significance: dict[str, MetricComparisonSignificance] = Field(default_factory=dict)


class RepeatStatsResponse(SdkBaseModel):
    repeat_count: int = 0
    seed: int = 42
    baseline: RepeatStatsSection | None = None
    attacked: RepeatStatsSection | None = None
    delta: RepeatStatsSection | None = None
    defended: RepeatStatsSection | None = None
    defense_delta: RepeatStatsSection | None = None


class RunSummary(SdkBaseModel):
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


class RunsListResponse(SdkBaseModel):
    items: list[RunSummary] = Field(default_factory=list)
    next_cursor: str | None = None
    total: int = 0


class RunArtifacts(SdkBaseModel):
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


class RunDetailResponse(SdkBaseModel):
    summary: RunSummary
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, object] | None = None
    target_retrieval: dict[str, object] | None = None
    repeat_stats: RepeatStatsResponse | None = None
    per_user: list[dict[str, object]] = Field(default_factory=list)
    manifest: dict[str, object] | None = None
    artifacts: RunArtifacts


class ExperimentRunLogEvent(SdkBaseModel):
    type: Literal["log"] = "log"
    line: str


class ExperimentRunCompleteEvent(SdkBaseModel):
    type: Literal["complete"] = "complete"
    summary: ExperimentRunResponse


class ExperimentRunFailedEvent(SdkBaseModel):
    type: Literal["failed"] = "failed"
    detail: str
    status_code: int
