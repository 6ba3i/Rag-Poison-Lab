from __future__ import annotations

from typing import Any

import httpx

from api.app.llm.http_retry import execute_with_retry


class OpenAIResponsesClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout: float = 30.0,
        max_retries: int = 1,
        retry_backoff_seconds: float = 0.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max(0, int(max_retries))
        self.retry_backoff_seconds = max(0.0, float(retry_backoff_seconds))

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
        payload: dict[str, Any] = {
            "model": model,
            "input": prompt,
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }
        if system:
            payload["instructions"] = system
        if json_schema is not None:
            payload["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": "response",
                    "schema": json_schema,
                }
            }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = execute_with_retry(
                send=lambda: httpx.post(
                    f"{self.base_url}/responses",
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                ),
                max_retries=self.max_retries,
                retry_backoff_seconds=self.retry_backoff_seconds,
            )
            body = response.json()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"OpenAI Responses request failed: {exc}") from exc

        return _extract_text(body)


def _extract_text(body: object) -> str:
    if not isinstance(body, dict):
        raise RuntimeError("OpenAI Responses response must be a JSON object")

    output_text = body.get("output_text")
    if isinstance(output_text, str):
        rendered = output_text.strip()
        if rendered:
            return rendered

    output = body.get("output")
    if not isinstance(output, list) or not output:
        raise RuntimeError("OpenAI Responses response missing output")

    parts: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for content_item in content:
            if not isinstance(content_item, dict):
                continue
            text = content_item.get("text")
            if isinstance(text, str):
                stripped = text.strip()
                if stripped:
                    parts.append(stripped)
                    continue
            if content_item.get("type") == "output_text":
                candidate = str(content_item.get("text", "")).strip()
                if candidate:
                    parts.append(candidate)

    joined = "\n".join(parts).strip()
    if joined:
        return joined

    raise RuntimeError("OpenAI Responses response did not include text content")
