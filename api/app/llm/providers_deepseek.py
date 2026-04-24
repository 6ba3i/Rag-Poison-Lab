from __future__ import annotations

from typing import Any

from api.app.llm.base import LlmProvider, ProviderStatus
from api.app.llm.openai_compatible import OpenAICompatibleClient


class DeepSeekProvider(LlmProvider):
    provider_name = "deepseek"

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        curated_models: list[str],
        base_url: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        super().__init__(model=model)
        self.api_key = api_key.strip() if api_key is not None else None
        self.curated_models = curated_models
        self.base_url = (base_url or "https://api.deepseek.com").strip() or "https://api.deepseek.com"
        self.timeout = timeout

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
            raise RuntimeError("DeepSeek provider is unavailable: missing API key environment configuration")
        client = OpenAICompatibleClient(base_url=self.base_url, api_key=api_key, timeout=self.timeout)
        return client.generate(
            model=self.model,
            prompt=prompt,
            system=system,
            json_schema=json_schema,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def healthcheck(self) -> ProviderStatus:
        available = self._resolve_api_key() is not None
        return ProviderStatus(
            provider=self.provider_name,
            available=available,
            healthy=available,
            message="" if available else "Missing API key environment configuration",
        )

    def list_models(self) -> list[str]:
        if self.curated_models:
            return self.curated_models
        return [self.model]

    def _resolve_api_key(self) -> str | None:
        if self.api_key is not None and self.api_key != "":
            return self.api_key
        return None
