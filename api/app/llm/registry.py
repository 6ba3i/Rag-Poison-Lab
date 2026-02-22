from __future__ import annotations

from pathlib import Path

from api.app.llm.local_ollama import check_ollama_connectivity, list_ollama_models
from api.app.settings import Settings
from common.schemas.api_types import LlmProviderOption

PROVIDERS: tuple[str, ...] = ("local", "chatgpt", "claude", "gemini", "qwen")


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
        secret_path = self.settings.provider_secret_paths.get(provider)
        if secret_path is None:
            return False
        return _secret_exists(secret_path)

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


def _secret_exists(path: Path) -> bool:
    try:
        return path.exists() and path.is_file() and path.read_text(encoding="utf-8").strip() != ""
    except Exception:  # noqa: BLE001
        return False


def _safe_yaml_load(path: Path) -> object:
    try:
        import yaml

        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
