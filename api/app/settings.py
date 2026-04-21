from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from elasticsearch import Elasticsearch
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from api.app.llm.registry import LlmRegistry


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
        env_file=(".env.key", ".env"),
        env_file_encoding="utf-8",
    )

    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_username: str | None = None
    elasticsearch_password: str | None = None
    elasticsearch_api_key: str | None = None
    elasticsearch_verify_ssl: bool = True
    elasticsearch_ca_bundle: Path | None = None
    elasticsearch_timeout_seconds: float = Field(default=10.0, gt=0)
    ollama_base_url: str = "http://localhost:11434"
    ollama_timeout_seconds: float = Field(default=60.0, gt=0)

    openai_compat_base_url: str | None = None
    openai_compat_api_key: str | None = None
    chatgpt_base_url: str | None = None
    chatgpt_api_key: str | None = None
    claude_base_url: str | None = None
    claude_api_key: str | None = None
    gemini_base_url: str | None = None
    gemini_api_key: str | None = None
    qwen_base_url: str | None = None
    qwen_api_key: str | None = None

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
    def resolved_attack_config_path(self) -> Path:
        return (self.resolved_config_dir / "attack_config.json").resolve()

    @property
    def resolved_defense_config_path(self) -> Path:
        return (self.resolved_config_dir / "defense_config.json").resolve()

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

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def _normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


@lru_cache(maxsize=8)
def _build_es_client(
    es_url: str,
    *,
    api_key: str | None,
    username: str | None,
    password: str | None,
    verify_ssl: bool,
    ca_bundle: Path | None,
    timeout_seconds: float,
) -> Elasticsearch:
    client_kwargs: dict[str, object] = {
        "verify_certs": verify_ssl,
        "request_timeout": timeout_seconds,
    }
    if verify_ssl and ca_bundle is not None:
        client_kwargs["ca_certs"] = str(ca_bundle)

    if api_key is not None:
        client_kwargs["api_key"] = api_key
    elif username is not None and password is not None:
        client_kwargs["basic_auth"] = (username, password)

    return Elasticsearch(es_url, **client_kwargs)


def get_es_client() -> Elasticsearch:
    settings = get_settings()
    return build_es_client(es_url=settings.elasticsearch_url, settings=settings)


def build_es_client(*, es_url: str, settings: Settings | None = None) -> Elasticsearch:
    resolved_settings = settings or get_settings()
    return _build_es_client(
        es_url,
        api_key=_normalize_optional(resolved_settings.elasticsearch_api_key),
        username=_normalize_optional(resolved_settings.elasticsearch_username),
        password=_normalize_optional(resolved_settings.elasticsearch_password),
        verify_ssl=resolved_settings.elasticsearch_verify_ssl,
        ca_bundle=resolved_settings.elasticsearch_ca_bundle.resolve()
        if resolved_settings.elasticsearch_ca_bundle is not None
        else None,
        timeout_seconds=float(resolved_settings.elasticsearch_timeout_seconds),
    )


@lru_cache(maxsize=1)
def _build_llm_registry() -> LlmRegistry:
    from api.app.llm.registry import LlmRegistry

    return LlmRegistry(settings=get_settings())


def get_llm_registry() -> LlmRegistry:
    return _build_llm_registry()
