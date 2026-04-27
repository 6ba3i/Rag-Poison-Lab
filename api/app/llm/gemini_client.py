from __future__ import annotations

from typing import Any

import httpx

from api.app.llm.http_retry import execute_with_retry


class GeminiClient:
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
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        if json_schema is not None:
            payload["generationConfig"]["responseMimeType"] = "application/json"
            payload["generationConfig"]["responseSchema"] = json_schema

        try:
            response = execute_with_retry(
                send=lambda: httpx.post(
                    f"{self.base_url}/models/{model}:generateContent",
                    params={"key": self.api_key},
                    json=payload,
                    timeout=self.timeout,
                ),
                max_retries=self.max_retries,
                retry_backoff_seconds=self.retry_backoff_seconds,
            )
            body = response.json()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Gemini request failed: {exc}") from exc

        return _extract_text(body)


def _extract_text(body: object) -> str:
    if not isinstance(body, dict):
        raise RuntimeError("Gemini response must be a JSON object")

    candidates = body.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise RuntimeError("Gemini response missing candidates")

    first = candidates[0]
    if not isinstance(first, dict):
        raise RuntimeError("Gemini response has malformed candidate")

    content = first.get("content")
    if not isinstance(content, dict):
        raise RuntimeError("Gemini response missing content")

    parts = content.get("parts")
    if not isinstance(parts, list) or not parts:
        raise RuntimeError("Gemini response missing parts")

    rendered: list[str] = []
    for item in parts:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        if text:
            rendered.append(text)

    joined = "\n".join(rendered).strip()
    if joined == "":
        raise RuntimeError("Gemini response did not include text content")
    return joined
