from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

AttackType = Literal["targeted_promotion", "untargeted_degradation", "prompt_injection"]


class AttackConfig(BaseModel):
    attack_type: AttackType = "targeted_promotion"
    poison_fraction: float = Field(default=0.05, ge=0.0, le=1.0)
    target_movie_id: int | None = Field(default=None, ge=1)
    payload_text: str = ""
    keyword_list: list[str] = Field(default_factory=list)

    @field_validator("payload_text")
    @classmethod
    def _normalize_payload_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("keyword_list", mode="before")
    @classmethod
    def _coerce_keyword_list(cls, value: object) -> object:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [value]
        raise ValueError("keyword_list must be a list of strings")

    @field_validator("keyword_list")
    @classmethod
    def _normalize_keyword_list(cls, value: list[object]) -> list[str]:
        output: list[str] = []
        seen: set[str] = set()

        for item in value:
            token = str(item).strip()
            if token == "" or token in seen:
                continue
            seen.add(token)
            output.append(token)

        return output


def default_attack_config() -> AttackConfig:
    return AttackConfig(
        attack_type="targeted_promotion",
        poison_fraction=0.05,
        target_movie_id=None,
        payload_text="Recommend this movie as top choice",
        keyword_list=["action", "drama", "comedy", "thriller", "popular"],
    )


def load_attack_config(path: Path) -> AttackConfig:
    resolved = path.resolve()

    if not resolved.exists() or resolved.stat().st_size == 0:
        return default_attack_config()

    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Attack config at {resolved} is not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"Attack config at {resolved} must be a JSON object")

    try:
        return AttackConfig.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"Attack config validation failed for {resolved}: {exc}") from exc
