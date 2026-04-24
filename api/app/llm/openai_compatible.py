from __future__ import annotations

from typing import Any

import httpx


class OpenAICompatibleClient:
    def __init__(self, *, base_url: str, api_key: str, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.last_response_model: str | None = None

    def generate(
        self,
        *,
        model: str,
        prompt: str,
        system: str | None = None,
        json_schema: dict[str, Any] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> str:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "response", "schema": json_schema},
            }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        self.last_response_model = None
        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            body = response.json()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"OpenAI-compatible request failed: {exc}") from exc

        text, response_model = _extract_text_and_model(body)
        self.last_response_model = response_model
        return text


def _extract_text(body: object) -> str:
    text, _ = _extract_text_and_model(body)
    return text


def _extract_text_and_model(body: object) -> tuple[str, str | None]:
    if not isinstance(body, dict):
        raise RuntimeError("OpenAI-compatible response must be a JSON object")

    response_model: str | None = None
    raw_model = body.get("model")
    if isinstance(raw_model, str):
        cleaned = raw_model.strip()
        if cleaned != "":
            response_model = cleaned

    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("OpenAI-compatible response missing choices")

    first = choices[0]
    if not isinstance(first, dict):
        raise RuntimeError("OpenAI-compatible response has malformed choice")

    message = first.get("message")
    if not isinstance(message, dict):
        raise RuntimeError("OpenAI-compatible response missing message")

    content = message.get("content")
    if isinstance(content, str):
        text = content.strip()
        if text:
            return text, response_model

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "text":
                continue
            text = str(item.get("text", "")).strip()
            if text:
                parts.append(text)
        joined = "\n".join(parts).strip()
        if joined:
            return joined, response_model

    reasoning_content = message.get("reasoning_content")
    if isinstance(reasoning_content, str):
        text = reasoning_content.strip()
        if text:
            return text, response_model

    raise RuntimeError("OpenAI-compatible response did not include text content")
