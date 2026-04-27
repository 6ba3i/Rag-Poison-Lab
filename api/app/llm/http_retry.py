from __future__ import annotations

import time
from collections.abc import Callable

import httpx

_RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}


def execute_with_retry(
    *,
    send: Callable[[], httpx.Response],
    max_retries: int = 1,
    retry_backoff_seconds: float = 0.0,
) -> httpx.Response:
    attempts = max(1, int(max_retries) + 1)
    backoff = max(0.0, float(retry_backoff_seconds))

    for attempt in range(attempts):
        try:
            response = send()
        except Exception as exc:  # noqa: BLE001
            if attempt < attempts - 1 and _is_retryable_exception(exc):
                _sleep_backoff(backoff=backoff, attempt=attempt)
                continue
            raise

        if response.status_code in _RETRYABLE_STATUS_CODES and attempt < attempts - 1:
            _sleep_backoff(backoff=backoff, attempt=attempt)
            continue

        response.raise_for_status()
        return response

    raise RuntimeError("HTTP request exhausted retry attempts")


def _is_retryable_exception(exc: Exception) -> bool:
    return isinstance(exc, httpx.TransportError)


def _sleep_backoff(*, backoff: float, attempt: int) -> None:
    if backoff <= 0.0:
        return
    time.sleep(backoff * float(attempt + 1))

