from __future__ import annotations

from pathlib import Path
from typing import Any

from api.app.llm.base import LlmProvider, ProviderStatus, read_secret_text


class ClaudeProvider(LlmProvider):
    provider_name = "claude"

    def __init__(self, *, model: str, api_key_file: Path, curated_models: list[str]) -> None:
        super().__init__(model=model)
        self.api_key_file = api_key_file
        self.curated_models = curated_models

    def generate(
        self,
        *,
        prompt: str,
        system: str | None = None,
        json_schema: dict[str, Any] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> str:
        api_key = read_secret_text(self.api_key_file)
        if api_key is None:
            raise RuntimeError("Claude provider is unavailable: missing API key secret file")
        raise NotImplementedError("Claude provider generate() is not implemented in MVP task 08")

    def healthcheck(self) -> ProviderStatus:
        available = read_secret_text(self.api_key_file) is not None
        if not available:
            return ProviderStatus(
                provider=self.provider_name,
                available=False,
                healthy=False,
                message="Missing API key secret file",
            )
        return ProviderStatus(
            provider=self.provider_name,
            available=True,
            healthy=False,
            message="Provider is selectable but generation is not implemented in MVP task 08",
        )

    def list_models(self) -> list[str]:
        if self.curated_models:
            return self.curated_models
        return [self.model]
