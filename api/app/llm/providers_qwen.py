from __future__ import annotations

from typing import Any

from api.app.llm.base import (
    LlmProvider,
    ProviderStatus,
    RerankGenerationOptions,
    RerankResponseFormatMode,
)
from api.app.llm.openai_compatible import OpenAICompatibleClient


class QwenProvider(LlmProvider):
    provider_name = "qwen"

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        curated_models: list[str],
        base_url: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 1,
        retry_backoff_seconds: float = 0.0,
    ) -> None:
        super().__init__(model=model)
        self.api_key = api_key.strip() if api_key is not None else None
        self.curated_models = curated_models
        self.base_url = (base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1").strip() or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        self.timeout = timeout
        self.max_retries = max(0, int(max_retries))
        self.retry_backoff_seconds = max(0.0, float(retry_backoff_seconds))
        self.last_response_model: str | None = None

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
        api_key = self._resolve_api_key()
        if api_key is None:
            raise RuntimeError("Qwen provider is unavailable: missing API key environment configuration")
        client = OpenAICompatibleClient(
            base_url=self.base_url,
            api_key=api_key,
            timeout=self.timeout,
            max_retries=self.max_retries,
            retry_backoff_seconds=self.retry_backoff_seconds,
        )
        text = client.generate(
            model=self.model,
            prompt=prompt,
            system=system,
            json_schema=json_schema,
            response_format_mode=response_format_mode,
            request_extras=request_extras,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        self.last_response_model = client.last_response_model
        return text

    def rerank_generation_options(self) -> RerankGenerationOptions:
        return RerankGenerationOptions(
            response_format_mode="json_object",
            json_object_key="order",
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
