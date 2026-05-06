from __future__ import annotations

from typing import Any

import httpx

from api.app.llm.base import RerankResponseFormatMode
from api.app.llm.http_retry import execute_with_retry


class OpenAICompatibleClient:
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
        self.last_response_model: str | None = None

    def generate(
        self,
        *,
        model: str,
        prompt: str,
        system: str | None = None,
        json_schema: dict[str, Any] | None = None,
        response_format_mode: RerankResponseFormatMode | None = None,
        request_extras: dict[str, Any] | None = None,
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
        resolved_mode = response_format_mode
        if resolved_mode is None and json_schema is not None:
            resolved_mode = "json_schema"

        if resolved_mode == "json_schema":
            if json_schema is None:
                raise RuntimeError("OpenAI-compatible json_schema mode requires json_schema")
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "response", "schema": json_schema},
            }
        elif resolved_mode == "json_object":
            payload["response_format"] = {"type": "json_object"}
        elif resolved_mode is not None:
            raise RuntimeError(f"OpenAI-compatible request does not support response_format_mode={resolved_mode!r}")

        if request_extras:
            payload.update(request_extras)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        self.last_response_model = None
        try:
            response = self._send_with_novai_fallback(
                headers=headers,
                payload=payload,
            )
            body = response.json()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"OpenAI-compatible request failed: {exc}") from exc

        text, response_model = _extract_text_and_model(body)
        self.last_response_model = response_model
        return text

    def _send_with_novai_fallback(
        self,
        *,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> httpx.Response:
        base_urls = [self.base_url]
        novai_fallback_base = "https://us.novaiapi.com/v1"
        if _is_novai_base_url(self.base_url) and self.base_url.rstrip("/") != novai_fallback_base:
            base_urls.append(novai_fallback_base)

        last_exc: Exception | None = None
        for base_index, base_url in enumerate(base_urls):

            def _send_request() -> httpx.Response:
                response = httpx.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )
                if response.status_code >= 400:
                    if _is_novai_upstream_bad_request(response):
                        raise _NovaiUpstreamBadRequest.from_response(response)
                    return response
                try:
                    response.json()
                except ValueError as exc:
                    raise httpx.ReadError(
                        "OpenAI-compatible response was not valid JSON",
                        request=getattr(response, "request", None),
                    ) from exc
                return response

            try:
                return execute_with_retry(
                    send=_send_request,
                    max_retries=self.max_retries,
                    retry_backoff_seconds=self.retry_backoff_seconds,
                )
            except _NovaiUpstreamBadRequest as exc:
                last_exc = exc
                if base_index < len(base_urls) - 1:
                    continue
                raise
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                raise

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("OpenAI-compatible request failed without response")


class _NovaiUpstreamBadRequest(httpx.TransportError):
    def __init__(self, message: str, *, request: httpx.Request | None = None, response: httpx.Response | None = None) -> None:
        super().__init__(message, request=request)
        self.response = response

    @classmethod
    def from_response(cls, response: httpx.Response) -> "_NovaiUpstreamBadRequest":
        request = getattr(response, "request", None)
        try:
            response_json = response.json()
        except Exception:  # noqa: BLE001
            response_json = None
        detail = _truncate_error_detail(_extract_novai_error_detail(response_json), limit=320)
        message = f"HTTP {response.status_code}"
        if detail is not None:
            message += f" ({detail})"
        return cls(message, request=request, response=response)


def _is_novai_base_url(base_url: str) -> bool:
    lowered = base_url.strip().lower()
    return "novai" in lowered


def _is_novai_upstream_bad_request(response: httpx.Response) -> bool:
    if response.status_code != 400:
        return False
    try:
        payload = response.json()
    except Exception:  # noqa: BLE001
        return False
    detail = _extract_novai_error_detail(payload)
    if detail is None:
        return False
    lowered = detail.lower()
    return "up_bad_request" in lowered or "请求失败" in detail


def _extract_novai_error_detail(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    error = payload.get("error")
    if isinstance(error, dict):
        for key in ("message", "code", "type"):
            value = error.get(key)
            if isinstance(value, str) and value.strip():
                text = value.strip()
                if key == "message":
                    return text
        return None
    if isinstance(error, str) and error.strip():
        return error.strip()
    return None


def _truncate_error_detail(value: str | None, *, limit: int) -> str | None:
    if value is None:
        return None
    compact = " ".join(value.split())
    if compact == "":
        return None
    if len(compact) <= limit:
        return compact
    return compact[:limit].rstrip() + "..."


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

    first_text = first.get("text")
    if isinstance(first_text, str):
        text = first_text.strip()
        if text:
            return text, response_model

    message = first.get("message")
    if not isinstance(message, dict):
        delta = first.get("delta")
        if isinstance(delta, dict):
            delta_content = delta.get("content")
            if isinstance(delta_content, str):
                text = delta_content.strip()
                if text:
                    return text, response_model
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
            item_type = item.get("type")
            if item_type not in {"text", "output_text", None}:
                continue
            text = str(item.get("text", "")).strip()
            if text:
                parts.append(text)
        joined = "\n".join(parts).strip()
        if joined:
            return joined, response_model

    tool_calls = message.get("tool_calls")
    if isinstance(tool_calls, list):
        for call in tool_calls:
            if not isinstance(call, dict):
                continue
            function_payload = call.get("function")
            if not isinstance(function_payload, dict):
                continue
            arguments = function_payload.get("arguments")
            if isinstance(arguments, str):
                text = arguments.strip()
                if text:
                    return text, response_model

    reasoning_content = message.get("reasoning_content")
    if isinstance(reasoning_content, str):
        text = reasoning_content.strip()
        if text:
            return text, response_model

    raise RuntimeError("OpenAI-compatible response did not include text content")
