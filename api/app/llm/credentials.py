from __future__ import annotations

from api.app.settings import Settings

_PROVIDER_API_KEY_ATTR = {
    "chatgpt": "chatgpt_api_key",
    "claude": "claude_api_key",
    "gemini": "gemini_api_key",
    "qwen": "qwen_api_key",
    "deepseek": "deepseek_api_key",
}
_PROVIDER_API_KEY_ENV = {
    "chatgpt": "CHATGPT_API_KEY",
    "claude": "CLAUDE_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "qwen": "QWEN_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
}
_PROVIDER_BASE_URL_ATTR = {
    "chatgpt": "chatgpt_base_url",
    "claude": "claude_base_url",
    "gemini": "gemini_base_url",
    "qwen": "qwen_base_url",
    "deepseek": "deepseek_base_url",
}
_PROVIDER_BASE_URL_ENV = {
    "chatgpt": "CHATGPT_BASE_URL",
    "claude": "CLAUDE_BASE_URL",
    "gemini": "GEMINI_BASE_URL",
    "qwen": "QWEN_BASE_URL",
    "deepseek": "DEEPSEEK_BASE_URL",
}
_OPENAI_COMPAT_PROVIDERS = {"chatgpt", "claude", "gemini"}
_OPENAI_COMPAT_API_KEY_ENV = "OPENAI_COMPAT_API_KEY"
_OPENAI_COMPAT_BASE_URL_ENV = "OPENAI_COMPAT_BASE_URL"


def resolve_api_key(
    provider_name: str,
    settings: Settings,
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

    if provider_name == "deepseek":
        return "https://api.deepseek.com", "default:DEEPSEEK_BASE_URL"

    return None, "none"


def _clean_value(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = raw.strip()
    if value == "":
        return None
    return value
