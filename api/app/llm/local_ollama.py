from __future__ import annotations

import httpx


def _tags_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/api/tags"


def check_ollama_connectivity(base_url: str, timeout: float = 3.0) -> bool:
    try:
        response = httpx.get(_tags_url(base_url), timeout=timeout)
        return response.status_code == 200
    except Exception:  # noqa: BLE001
        return False


def list_ollama_models(base_url: str, timeout: float = 3.0) -> list[str]:
    try:
        response = httpx.get(_tags_url(base_url), timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except Exception:  # noqa: BLE001
        return []

    models_raw = payload.get("models") if isinstance(payload, dict) else []
    if not isinstance(models_raw, list):
        return []

    names: set[str] = set()
    for item in models_raw:
        if isinstance(item, dict):
            name = str(item.get("name", "")).strip()
            if name:
                names.add(name)
    return sorted(names)
