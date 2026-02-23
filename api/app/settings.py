from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from elasticsearch import Elasticsearch
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    elasticsearch_url: str = "http://elasticsearch:9200"
    ollama_base_url: str = "http://localhost:11434"

    chatgpt_api_key_file: Path = Path("/run/secrets/chatgpt_api_key")
    claude_api_key_file: Path = Path("/run/secrets/claude_api_key")
    gemini_api_key_file: Path = Path("/run/secrets/gemini_api_key")
    qwen_api_key_file: Path = Path("/run/secrets/qwen_api_key")

    repo_root: Path = Path(__file__).resolve().parents[2]
    data_root: Path | None = None
    config_root: Path | None = None
    processed_root: Path | None = None
    static_root: Path | None = None
    llm_models_file: Path | None = None

    @property
    def resolved_data_root(self) -> Path:
        if self.data_root is not None:
            return self.data_root.resolve()

        workspace_data = Path("/workspace/data")
        if workspace_data.exists():
            return workspace_data.resolve()

        return (self.repo_root / "data").resolve()

    @property
    def resolved_config_dir(self) -> Path:
        if self.config_root is not None:
            path = self.config_root.resolve()
        else:
            path = (self.resolved_data_root / "config").resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def resolved_processed_dir(self) -> Path:
        if self.processed_root is not None:
            return self.processed_root.resolve()
        return (self.resolved_data_root / "processed").resolve()

    @property
    def resolved_llm_config_path(self) -> Path:
        return (self.resolved_config_dir / "llm_config.json").resolve()

    @property
    def resolved_llm_models_path(self) -> Path:
        if self.llm_models_file is not None:
            return self.llm_models_file.resolve()
        return (self.repo_root / "conf" / "llm_models.yaml").resolve()

    @property
    def resolved_static_dir(self) -> Path:
        if self.static_root is not None:
            return self.static_root.resolve()
        return (self.repo_root / "api" / "app" / "static").resolve()

    @property
    def provider_secret_paths(self) -> dict[str, Path]:
        return {
            "chatgpt": self.chatgpt_api_key_file,
            "claude": self.claude_api_key_file,
            "gemini": self.gemini_api_key_file,
            "qwen": self.qwen_api_key_file,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


@lru_cache(maxsize=4)
def _build_es_client(es_url: str) -> Elasticsearch:
    return Elasticsearch(es_url)


def get_es_client() -> Elasticsearch:
    settings = get_settings()
    return _build_es_client(settings.elasticsearch_url)


@lru_cache(maxsize=1)
def _build_llm_registry() -> "LlmRegistry":
    from api.app.llm.registry import LlmRegistry

    return LlmRegistry(settings=get_settings())


def get_llm_registry() -> "LlmRegistry":
    return _build_llm_registry()
