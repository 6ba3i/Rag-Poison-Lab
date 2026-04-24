from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

ProviderName = Literal["local", "chatgpt", "claude", "gemini", "qwen", "deepseek"]
RankingMode = Literal["deterministic", "llm_rerank"]
RetrievalMode = Literal["lexical", "dense", "hybrid"]

_QWEN_MODEL_ALIASES: dict[str, str] = {
    "qwen3.5-plus": "qwen-3.5-plus",
}
_DEEPSEEK_MODEL_ALIASES: dict[str, str] = {
    "deepseek-reasoner": "deepseek-v4-pro",
    "deepseek-chat": "deepseek-v4-pro",
}


def canonicalize_model_name(*, provider: ProviderName, model: str) -> str:
    if provider == "qwen":
        return _QWEN_MODEL_ALIASES.get(model, model)
    if provider == "deepseek":
        return _DEEPSEEK_MODEL_ALIASES.get(model, model)
    return model


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

    @model_validator(mode="after")
    def _canonicalize_model_aliases(self) -> "LlmRoleConfig":
        self.model = canonicalize_model_name(provider=self.provider, model=self.model)
        return self


class LlmConfig(BaseModel):
    victim: LlmRoleConfig
    attacker: LlmRoleConfig
    ranking_mode: RankingMode = "deterministic"
    retrieval_mode: RetrievalMode = "lexical"


def default_llm_config() -> LlmConfig:
    return LlmConfig(
        victim=LlmRoleConfig(provider="local", model="qwen2.5:1.5b"),
        attacker=LlmRoleConfig(provider="local", model="qwen2.5:1.5b"),
        ranking_mode="deterministic",
        retrieval_mode="lexical",
    )
