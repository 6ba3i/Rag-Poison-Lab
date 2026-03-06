from __future__ import annotations

from typing import Any

import httpx

from api.app.llm.base import LlmProvider, ProviderStatus


def _tags_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/api/tags"


def _generate_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/api/generate"


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


class LocalOllamaProvider(LlmProvider):
    provider_name = "local"

    def __init__(self, *, base_url: str, model: str, timeout: float = 20.0) -> None:
        super().__init__(model=model)
        self.base_url = base_url
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
        options: dict[str, Any] = {"temperature": temperature, "num_predict": max_tokens}
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "system": system or "",
            "stream": False,
            "options": options,
        }
        if json_schema is not None:
            payload["format"] = json_schema

        try:
            response = httpx.post(_generate_url(self.base_url), json=payload, timeout=self.timeout)
            response.raise_for_status()
            body = response.json()
        except httpx.TimeoutException as exc:
            raise RuntimeError(
                f"Ollama request timed out after {self.timeout:.1f}s "
                f"(model={self.model}, base_url={self.base_url})"
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Ollama request failed: {exc}") from exc

        text = str(body.get("response", "")).strip() if isinstance(body, dict) else ""
        if text == "":
            raise RuntimeError("Ollama response did not include text output")
        return text

    def healthcheck(self) -> ProviderStatus:
        healthy = check_ollama_connectivity(self.base_url, timeout=3.0)
        message = "" if healthy else "Unable to reach Ollama tags endpoint"
        return ProviderStatus(
            provider=self.provider_name,
            available=healthy,
            healthy=healthy,
            message=message,
        )

    def list_models(self) -> list[str]:
        return list_ollama_models(self.base_url, timeout=3.0)
