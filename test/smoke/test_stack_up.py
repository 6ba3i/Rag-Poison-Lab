from __future__ import annotations

import os

import httpx
import pytest


pytestmark = pytest.mark.integration


def _api_base_url() -> str:
    return os.getenv("RAGPOISON_API_URL", "http://localhost:8000").rstrip("/")


def test_health_endpoint_contract() -> None:
    url = f"{_api_base_url()}/api/health"

    try:
        response = httpx.get(url, timeout=8.0)
    except httpx.RequestError as exc:
        pytest.skip(f"API stack not reachable at {url}: {exc}")

    if response.status_code != 200:
        pytest.skip(f"Health endpoint unavailable ({response.status_code}) at {url}")

    payload = response.json()
    assert payload.get("status") == "ok"
    assert isinstance(payload.get("elasticsearch_connected"), bool)
    assert isinstance(payload.get("ollama_connected"), bool)
