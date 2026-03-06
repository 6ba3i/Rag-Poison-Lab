from __future__ import annotations

import logging
from pathlib import Path

from api.app.llm.base import read_secret_text
from api.app.settings import Settings

logger = logging.getLogger(__name__)

_PROVIDER_API_KEY_ATTR = {
    "chatgpt": "chatgpt_api_key",
    "claude": "claude_api_key",
    "gemini": "gemini_api_key",
    "qwen": "qwen_api_key",
}
_PROVIDER_API_KEY_ENV = {
    "chatgpt": "CHATGPT_API_KEY",
    "claude": "CLAUDE_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "qwen": "QWEN_API_KEY",
}
_PROVIDER_BASE_URL_ATTR = {
    "chatgpt": "chatgpt_base_url",
    "claude": "claude_base_url",
    "gemini": "gemini_base_url",
    "qwen": "qwen_base_url",
}
_PROVIDER_BASE_URL_ENV = {
    "chatgpt": "CHATGPT_BASE_URL",
    "claude": "CLAUDE_BASE_URL",
    "gemini": "GEMINI_BASE_URL",
    "qwen": "QWEN_BASE_URL",
}
_PROVIDER_API_KEY_FILE_ENV = {
    "chatgpt": "CHATGPT_API_KEY_FILE",
    "claude": "CLAUDE_API_KEY_FILE",
    "gemini": "GEMINI_API_KEY_FILE",
    "qwen": "QWEN_API_KEY_FILE",
}
_OPENAI_COMPAT_PROVIDERS = {"chatgpt", "claude", "gemini"}
_OPENAI_COMPAT_API_KEY_ENV = "OPENAI_COMPAT_API_KEY"
_OPENAI_COMPAT_BASE_URL_ENV = "OPENAI_COMPAT_BASE_URL"


def resolve_api_key(
    provider_name: str,
    settings: Settings,
    *,
    warn_on_file_fallback: bool = True,
) -> tuple[str | None, str]:
    provider_attr = _PROVIDER_API_KEY_ATTR.get(provider_name)
    provider_env = _PROVIDER_API_KEY_ENV.get(provider_name)
    if provider_attr is not None and provider_env is not None:
        value = _clean_value(getattr(settings, provider_attr, None))
        if value is not None:
            return value, f"env:{provider_env}"

    if provider_name in _OPENAI_COMPAT_PROVIDERS:
        shared_value = _clean_value(settings.openai_compat_api_key)
        if shared_value is not None:
            return shared_value, f"env:{_OPENAI_COMPAT_API_KEY_ENV}"

    secret_path = settings.provider_secret_paths.get(provider_name)
    if secret_path is not None:
        legacy_value = read_secret_text(secret_path)
        if legacy_value is not None:
            if warn_on_file_fallback:
                _warn_file_fallback(
                    provider_name=provider_name,
                    secret_path=secret_path,
                    recommended_env=provider_env,
                )
            file_env = _PROVIDER_API_KEY_FILE_ENV.get(provider_name, "API_KEY_FILE")
            return legacy_value, f"file:{file_env}"

    return None, "none"


def resolve_base_url(provider_name: str, settings: Settings) -> tuple[str | None, str]:
    provider_attr = _PROVIDER_BASE_URL_ATTR.get(provider_name)
    provider_env = _PROVIDER_BASE_URL_ENV.get(provider_name)

    if provider_attr is not None and provider_env is not None:
        provider_url = _clean_value(getattr(settings, provider_attr, None))
        if provider_url is not None:
            return provider_url, f"env:{provider_env}"

    if provider_name == "chatgpt":
        shared_url = _clean_value(settings.openai_compat_base_url)
        if shared_url is not None:
            return shared_url, f"env:{_OPENAI_COMPAT_BASE_URL_ENV}"
        return "https://api.openai.com/v1", "default:CHATGPT_BASE_URL"

    return None, "none"


def _warn_file_fallback(*, provider_name: str, secret_path: Path, recommended_env: str | None) -> None:
    if recommended_env is None:
        recommended = "set provider env vars"
    else:
        recommended = f"set {recommended_env}"
    logger.warning(
        "Provider '%s' is using deprecated API key file fallback (%s). Please %s.",
        provider_name,
        secret_path,
        recommended,
    )


def _clean_value(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = raw.strip()
    if value == "":
        return None
    return value
