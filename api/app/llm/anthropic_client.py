from __future__ import annotations

import json
from typing import Any

import httpx


class AnthropicClient:
    def __init__(self, *, base_url: str, api_key: str, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

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
        resolved_system = system
        if json_schema is not None:
            schema_instruction = (
                "Return valid JSON only. The JSON must conform to this schema: "
                + json.dumps(json_schema, sort_keys=True, ensure_ascii=False)
            )
            resolved_system = f"{resolved_system}\n\n{schema_instruction}".strip() if resolved_system else schema_instruction

        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if resolved_system:
            payload["system"] = resolved_system

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        try:
            response = httpx.post(
                f"{self.base_url}/messages",
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            body = response.json()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Claude request failed: {exc}") from exc

        return _extract_text(body)


def _extract_text(body: object) -> str:
    if not isinstance(body, dict):
        raise RuntimeError("Claude response must be a JSON object")

    content = body.get("content")
    if not isinstance(content, list) or not content:
        raise RuntimeError("Claude response missing content blocks")

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
    if joined == "":
        raise RuntimeError("Claude response did not include text content")
    return joined
