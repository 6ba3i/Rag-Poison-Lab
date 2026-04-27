from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


@dataclass(frozen=True)
class ProviderStatus:
    provider: str
    available: bool
    healthy: bool
    message: str = ""


RerankResponseFormatMode = Literal["json_schema", "json_object"]


@dataclass(frozen=True)
class RerankGenerationOptions:
    response_format_mode: RerankResponseFormatMode = "json_schema"
    json_object_key: str | None = None
    request_extras: dict[str, Any] | None = None


class LlmProvider(ABC):
    provider_name: str

    def __init__(self, *, model: str) -> None:
        self.model = model

    @abstractmethod
    def generate(
        self,
        *,
        prompt: str,
        system: str | None = None,
        json_schema: dict[str, Any] | None = None,
        response_format_mode: RerankResponseFormatMode | None = None,
        request_extras: dict[str, Any] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> str:
        raise NotImplementedError

    def rerank_generation_options(self) -> RerankGenerationOptions:
        return RerankGenerationOptions()

    @abstractmethod
    def healthcheck(self) -> ProviderStatus:
        raise NotImplementedError

    @abstractmethod
    def list_models(self) -> list[str]:
        raise NotImplementedError


def read_secret_text(path: Path) -> str | None:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except Exception:  # noqa: BLE001
        return None
    if value == "":
        return None
    return value


def secret_exists(path: Path) -> bool:
    return read_secret_text(path) is not None
