from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

ProviderName = Literal["local", "chatgpt", "claude", "gemini", "qwen"]
RankingMode = Literal["deterministic", "llm_rerank"]


class LlmRoleConfig(BaseModel):
    provider: ProviderName = "local"
    model: str = Field(min_length=1, max_length=200)

    @field_validator("model")
    @classmethod
    def _normalize_model(cls, value: str) -> str:
        normalized = value.strip()
        if normalized == "":
            raise ValueError("model must not be empty")
        return normalized


class LlmConfig(BaseModel):
    victim: LlmRoleConfig
    attacker: LlmRoleConfig
    ranking_mode: RankingMode = "deterministic"


def default_llm_config() -> LlmConfig:
    return LlmConfig(
        victim=LlmRoleConfig(provider="local", model="qwen2.5:1.5b"),
        attacker=LlmRoleConfig(provider="local", model="qwen2.5:1.5b"),
        ranking_mode="deterministic",
    )
