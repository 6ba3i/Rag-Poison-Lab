from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

RecommendationMode = Literal["baseline", "attacked"]
HistorySplit = Literal["train", "all"]
ProviderName = Literal["local", "chatgpt", "claude", "gemini", "qwen"]
RankingMode = Literal["deterministic", "llm_rerank"]


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
    retrieval_query: str
    retrieved_docs: list[TraceDoc]
    rerank_candidates: list[TraceRerankCandidate] | None = None
    rerank_prompt: str | None = None
    rerank_raw_response: str | None = None
    rerank_parsed_order: list[int] | None = None
    rerank_fallback: bool | None = None


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
