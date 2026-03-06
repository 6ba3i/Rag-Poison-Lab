from __future__ import annotations

from pathlib import Path
from typing import Any

from api.app.llm.base import LlmProvider, ProviderStatus, read_secret_text


class GeminiProvider(LlmProvider):
    provider_name = "gemini"

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        api_key_file: Path | None = None,
        curated_models: list[str],
        base_url: str | None = None,
    ) -> None:
        super().__init__(model=model)
        self.api_key = api_key.strip() if api_key is not None else None
        self.api_key_file = api_key_file
        self.curated_models = curated_models
        self.base_url = (base_url or "").strip() or None

    def generate(
        self,
        *,
        prompt: str,
        system: str | None = None,
        json_schema: dict[str, Any] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> str:
        api_key = self._resolve_api_key()
        if api_key is None:
            raise RuntimeError("Gemini provider is unavailable: missing API key (env or secret file)")
        raise NotImplementedError("Gemini provider generate() is not implemented in MVP task 08")

    def healthcheck(self) -> ProviderStatus:
        available = self._resolve_api_key() is not None
        if not available:
            return ProviderStatus(
                provider=self.provider_name,
                available=False,
                healthy=False,
                message="Missing API key (env or secret file)",
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

    def _resolve_api_key(self) -> str | None:
        if self.api_key is not None and self.api_key != "":
            return self.api_key
        if self.api_key_file is None:
            return None
        return read_secret_text(self.api_key_file)
