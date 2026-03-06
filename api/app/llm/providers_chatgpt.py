from __future__ import annotations

from pathlib import Path
from typing import Any

from api.app.llm.base import LlmProvider, ProviderStatus, read_secret_text
from api.app.llm.openai_compatible import OpenAICompatibleClient


class ChatGptProvider(LlmProvider):
    provider_name = "chatgpt"

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        api_key_file: Path | None = None,
        curated_models: list[str],
        base_url: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        super().__init__(model=model)
        self.api_key = api_key.strip() if api_key is not None else None
        self.api_key_file = api_key_file
        self.curated_models = curated_models
        self.base_url = (base_url or "https://api.openai.com/v1").strip() or "https://api.openai.com/v1"
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
            raise RuntimeError("ChatGPT provider is unavailable: missing API key (env or secret file)")

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
        message = "" if available else "Missing API key (env or secret file)"
        return ProviderStatus(
            provider=self.provider_name,
            available=available,
            healthy=available,
            message=message,
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
