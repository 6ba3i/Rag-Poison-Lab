from __future__ import annotations

import json
from pathlib import Path

from api.app.llm.base import LlmProvider
from api.app.llm.credentials import resolve_api_key, resolve_base_url
from api.app.llm.local_ollama import LocalOllamaProvider, check_ollama_connectivity, list_ollama_models
from api.app.llm.providers_chatgpt import ChatGptProvider
from api.app.llm.providers_claude import ClaudeProvider
from api.app.llm.providers_gemini import GeminiProvider
from api.app.llm.providers_qwen import QwenProvider
from api.app.settings import Settings
from common.schemas.api_types import LlmProviderOption
from common.schemas.llm_config import LlmConfig, default_llm_config

PROVIDERS: tuple[str, ...] = ("local", "chatgpt", "claude", "gemini", "qwen")
PROVIDER_CLASSES = {
    "local": LocalOllamaProvider,
    "chatgpt": ChatGptProvider,
    "claude": ClaudeProvider,
    "gemini": GeminiProvider,
    "qwen": QwenProvider,
}


class LlmRegistry:
    def __init__(self, *, settings: Settings) -> None:
        self.settings = settings

    def ollama_connectivity(self) -> bool:
        return check_ollama_connectivity(self.settings.ollama_base_url)

    def list_local_models(self) -> list[str]:
        return list_ollama_models(self.settings.ollama_base_url)

    def _load_cloud_models(self) -> dict[str, list[str]]:
        path = self.settings.resolved_llm_models_path
        if not path.exists() or not path.is_file() or path.stat().st_size == 0:
            return {}

        parsed = _safe_yaml_load(path)
        if not isinstance(parsed, dict):
            return {}

        output: dict[str, list[str]] = {}
        for provider in PROVIDERS:
            if provider == "local":
                continue
            raw_value = parsed.get(provider)
            if not isinstance(raw_value, list):
                output[provider] = []
                continue
            models = [str(item).strip() for item in raw_value if str(item).strip()]
            output[provider] = models
        return output

    def _provider_is_available(self, provider: str) -> bool:
        if provider == "local":
            return True
        api_key, _ = resolve_api_key(provider_name=provider, settings=self.settings, warn_on_file_fallback=False)
        return api_key is not None

    def list_provider_options(self) -> list[LlmProviderOption]:
        cloud_models = self._load_cloud_models()
        local_models = self.list_local_models()

        options: list[LlmProviderOption] = []
        for provider in PROVIDERS:
            models = local_models if provider == "local" else cloud_models.get(provider, [])
            options.append(
                LlmProviderOption(
                    provider=provider,
                    available=self._provider_is_available(provider),
                    models=models,
                )
            )
        return options

    def get_provider_client(self, *, provider: str, model: str) -> LlmProvider:
        provider_cls = PROVIDER_CLASSES.get(provider)
        if provider_cls is None:
            raise KeyError(f"Unknown provider: {provider}")

        if provider == "local":
            return provider_cls(
                base_url=self.settings.ollama_base_url,
                model=model,
                timeout=float(self.settings.ollama_timeout_seconds),
            )

        secret_path = self.settings.provider_secret_paths.get(provider)
        if secret_path is None:
            raise KeyError(f"Missing secret path configuration for provider: {provider}")

        resolved_api_key, _ = resolve_api_key(provider_name=provider, settings=self.settings)
        resolved_base_url, _ = resolve_base_url(provider_name=provider, settings=self.settings)
        curated_models = self._load_cloud_models().get(provider, [])
        return provider_cls(
            model=model,
            api_key=resolved_api_key,
            api_key_file=secret_path,
            curated_models=curated_models,
            base_url=resolved_base_url,
        )

    def get_victim_client(self) -> LlmProvider:
        config = self._load_llm_config()
        return self.get_provider_client(provider=config.victim.provider, model=config.victim.model)

    def get_attacker_client(self) -> LlmProvider:
        config = self._load_llm_config()
        return self.get_provider_client(provider=config.attacker.provider, model=config.attacker.model)

    def _load_llm_config(self) -> LlmConfig:
        path = self.settings.resolved_llm_config_path
        if not path.exists() or not path.is_file() or path.stat().st_size == 0:
            return default_llm_config()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return LlmConfig.model_validate(payload)
        except Exception:  # noqa: BLE001
            return default_llm_config()


def _safe_yaml_load(path: Path) -> object:
    try:
        import yaml

        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
