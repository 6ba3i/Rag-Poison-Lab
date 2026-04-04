from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from common.schemas.llm_config import LlmConfig, ProviderName, RankingMode

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
    retrieval_query: str
    retrieved_docs: list[TraceDoc]
    rerank_candidates: list[TraceRerankCandidate] | None = None
    rerank_prompt: str | None = None
    rerank_raw_response: str | None = None
    rerank_parsed_order: list[int] | None = None
    rerank_fallback: bool | None = None


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


class ExperimentRunResponse(BaseModel):
    label: str | None = None
    prepare: dict[str, Any] | None = None
    index: dict[str, Any] | None = None
    eval: dict[str, Any] | None = None
    report: dict[str, Any] | None = None
    run_dir: str | None = None
