from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import httpx
import yaml

from api.app.settings import Settings

CLOUD_PROVIDERS: tuple[str, ...] = ("chatgpt", "claude", "gemini", "qwen", "deepseek")
OPENAI_MODELS_URL = "https://api.openai.com/v1/models"
ANTHROPIC_MODELS_URL = "https://api.anthropic.com/v1/models"
GEMINI_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"
QWEN_COMPAT_MODELS_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/models"
QWEN_MODELS_URL = "https://dashscope.aliyuncs.com/api/v1/models"
DEEPSEEK_DEFAULT_BASE_URL = "https://api.deepseek.com"


def refresh_cloud_model_catalog(
    *,
    settings: Settings,
    providers: Iterable[str] | None = None,
    timeout: float = 30.0,
) -> dict[str, list[str]]:
    selected = tuple(_normalize_providers(providers))
    catalog: dict[str, list[str]] = {}

    for provider in selected:
        if provider == "chatgpt":
            catalog[provider] = fetch_openai_model_catalog(settings=settings, timeout=timeout)
        elif provider == "claude":
            catalog[provider] = fetch_anthropic_model_catalog(settings=settings, timeout=timeout)
        elif provider == "gemini":
            catalog[provider] = fetch_gemini_model_catalog(settings=settings, timeout=timeout)
        elif provider == "qwen":
            catalog[provider] = fetch_qwen_model_catalog(settings=settings, timeout=timeout)
        elif provider == "deepseek":
            catalog[provider] = fetch_deepseek_model_catalog(settings=settings, timeout=timeout)
        else:
            raise KeyError(f"Unknown cloud provider: {provider}")

    return catalog


def write_cloud_model_catalog(*, path: Path, catalog: dict[str, list[str]]) -> None:
    payload = {provider: catalog[provider] for provider in CLOUD_PROVIDERS if provider in catalog}
    serialized = yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialized, encoding="utf-8")


def fetch_openai_model_catalog(*, settings: Settings, timeout: float = 30.0) -> list[str]:
    api_key = _require_provider_key(settings.chatgpt_api_key, provider="chatgpt")
    response = httpx.get(
        OPENAI_MODELS_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data", [])
    return filter_openai_model_ids(data)


def fetch_anthropic_model_catalog(*, settings: Settings, timeout: float = 30.0) -> list[str]:
    api_key = _require_provider_key(settings.claude_api_key, provider="claude")
    response = httpx.get(
        ANTHROPIC_MODELS_URL,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data", [])
    return filter_anthropic_model_ids(data)


def fetch_gemini_model_catalog(*, settings: Settings, timeout: float = 30.0) -> list[str]:
    api_key = _require_provider_key(settings.gemini_api_key, provider="gemini")
    response = httpx.get(
        GEMINI_MODELS_URL,
        params={"key": api_key},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("models", [])
    return filter_gemini_model_ids(data)


def fetch_qwen_model_catalog(*, settings: Settings, timeout: float = 30.0) -> list[str]:
    api_key = _require_provider_key(settings.qwen_api_key, provider="qwen")
    headers = {"Authorization": f"Bearer {api_key}"}

    compat_response = httpx.get(QWEN_COMPAT_MODELS_URL, headers=headers, timeout=timeout)
    compat_response.raise_for_status()
    compat_data = compat_response.json().get("data", [])

    full_models: list[dict[str, Any]] = []
    page_no = 1
    total = None
    while total is None or len(full_models) < total:
        response = httpx.get(
            QWEN_MODELS_URL,
            headers=headers,
            params={"page_no": page_no, "page_size": 100},
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json().get("output", {})
        page_models = payload.get("models", [])
        total = payload.get("total")
        if not isinstance(page_models, list) or not page_models:
            break
        full_models.extend(item for item in page_models if isinstance(item, dict))
        page_no += 1

    return filter_qwen_model_ids(compat_data=compat_data, model_data=full_models)


def fetch_deepseek_model_catalog(*, settings: Settings, timeout: float = 30.0) -> list[str]:
    api_key = _require_provider_key(settings.deepseek_api_key, provider="deepseek")
    base_url = (settings.deepseek_base_url or DEEPSEEK_DEFAULT_BASE_URL).strip() or DEEPSEEK_DEFAULT_BASE_URL
    response = httpx.get(
        f"{base_url.rstrip('/')}/models",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data", [])
    return filter_deepseek_model_ids(data)


def filter_openai_model_ids(data: object) -> list[str]:
    if not isinstance(data, list):
        return []

    selected: list[str] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id", "")).strip()
        if not model_id.startswith("gpt-"):
            continue
        lowered = model_id.lower()
        if any(token in lowered for token in ("audio", "transcribe", "tts", "realtime", "search", "image", "computer-use")):
            continue
        if lowered.startswith("gpt-3.5"):
            continue
        if lowered == "gpt-4" or lowered.startswith("gpt-4-") or lowered.startswith("gpt-4-turbo"):
            continue
        selected.append(model_id)

    return _dedupe(selected)


def filter_anthropic_model_ids(data: object) -> list[str]:
    if not isinstance(data, list):
        return []

    selected: list[str] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id", "")).strip()
        if model_id.startswith("claude-"):
            selected.append(model_id)
    return _dedupe(selected)


def filter_gemini_model_ids(data: object) -> list[str]:
    if not isinstance(data, list):
        return []

    selected: list[str] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        raw_name = str(item.get("name", "")).strip()
        model_id = raw_name.split("/", 1)[-1]
        if not model_id.startswith("gemini-"):
            continue

        methods = item.get("supportedGenerationMethods", [])
        if not isinstance(methods, list) or "generateContent" not in methods:
            continue

        lowered = model_id.lower()
        if any(
            token in lowered
            for token in ("audio", "image", "tts", "embedding", "robotics", "computer-use", "deep-research")
        ):
            continue

        selected.append(model_id)

    return _dedupe(selected)


def filter_qwen_model_ids(*, compat_data: object, model_data: object) -> list[str]:
    compat_ids = _extract_qwen_compatible_ids(compat_data)
    if not isinstance(model_data, list):
        return []

    selected: list[str] = []
    for item in model_data:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("model", "")).strip()
        if model_id == "" or model_id not in compat_ids:
            continue

        lowered = model_id.lower()
        if not lowered.startswith("qwen"):
            continue
        if any(
            token in lowered
            for token in (
                "image",
                "audio",
                "vl",
                "omni",
                "doc",
                "math",
                "asr",
                "livetranslate",
                "mt-",
                "deep-research",
                "character",
                "coder",
                "thinking",
                "realtime",
            )
        ):
            continue

        metadata = item.get("inference_metadata", {})
        response_modality = metadata.get("response_modality", []) if isinstance(metadata, dict) else []
        if not isinstance(response_modality, list) or "Text" not in response_modality:
            continue

        selected.append(model_id)

    return _dedupe(selected)


def filter_deepseek_model_ids(data: object) -> list[str]:
    if not isinstance(data, list):
        return []

    selected: list[str] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id", "")).strip()
        if not model_id.startswith("deepseek-"):
            continue

        lowered = model_id.lower()
        if any(token in lowered for token in ("audio", "image", "vision", "vl", "embedding", "tts", "asr")):
            continue
        selected.append(model_id)

    return _dedupe(selected)


def dump_catalog_json(catalog: dict[str, list[str]]) -> str:
    return json.dumps(catalog, indent=2, sort_keys=True) + "\n"


def _extract_qwen_compatible_ids(compat_data: object) -> set[str]:
    if not isinstance(compat_data, list):
        return set()
    ids: set[str] = set()
    for item in compat_data:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id", "")).strip()
        if model_id:
            ids.add(model_id)
    return ids


def _normalize_providers(providers: Iterable[str] | None) -> list[str]:
    if providers is None:
        return list(CLOUD_PROVIDERS)

    selected: list[str] = []
    for provider in providers:
        normalized = str(provider).strip().lower()
        if normalized == "":
            continue
        if normalized not in CLOUD_PROVIDERS:
            raise ValueError(f"Unknown provider: {provider}")
        if normalized not in selected:
            selected.append(normalized)
    return selected or list(CLOUD_PROVIDERS)


def _require_provider_key(raw_value: str | None, *, provider: str) -> str:
    if raw_value is None or raw_value.strip() == "":
        raise RuntimeError(f"{provider} model refresh requires a provider-specific API key in the environment")
    return raw_value.strip()


def _dedupe(values: Iterable[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        output.append(value)
        seen.add(value)
    return output
