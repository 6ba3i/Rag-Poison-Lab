from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from common.schemas.llm_config import LlmConfig, ProviderName

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


class TraceResponse(BaseModel):
    user_id: int
    mode: RecommendationMode
    retrieval_query: str
    retrieved_docs: list[TraceDoc]


class LlmProviderOption(BaseModel):
    provider: ProviderName
    available: bool
    models: list[str]


class LlmSettingsOptionsResponse(BaseModel):
    providers: list[LlmProviderOption]


class LlmSettingsResponse(BaseModel):
    config: LlmConfig
