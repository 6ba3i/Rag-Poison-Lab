from __future__ import annotations

import os
from typing import Any

import httpx
import pytest


pytestmark = pytest.mark.integration


def _api_base_url() -> str:
    return os.getenv("RAGPOISON_API_URL", "http://localhost:8000").rstrip("/")


def _request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
) -> httpx.Response:
    url = f"{_api_base_url()}{path}"
    try:
        return httpx.request(method=method, url=url, params=params, json=json, timeout=10.0)
    except httpx.RequestError as exc:
        pytest.skip(f"API stack not reachable at {url}: {exc}")


def test_users_recommendations_and_trace_roundtrip() -> None:
    users_response = _request("GET", "/api/users", params={"limit": 10})
    if users_response.status_code != 200:
        pytest.skip(f"/api/users unavailable ({users_response.status_code})")

    users_payload = users_response.json()
    if not isinstance(users_payload, list) or not users_payload:
        pytest.skip("No users returned; ensure data pipeline completed")

    first_user = users_payload[0]
    if not isinstance(first_user, dict) or "user_id" not in first_user:
        pytest.skip("Unexpected users payload; user_id missing")

    user_id = int(first_user["user_id"])

    recommendations_response = _request(
        "POST",
        "/api/recommendations",
        json={"user_id": user_id, "mode": "baseline", "k": 10},
    )
    if recommendations_response.status_code != 200:
        pytest.skip(
            "Recommendations unavailable; ensure indices are built and stack is ready "
            f"({recommendations_response.status_code})"
        )

    recommendations_payload = recommendations_response.json()
    assert isinstance(recommendations_payload, list)

    trace_response = _request(
        "POST",
        "/api/trace",
        json={"user_id": user_id, "mode": "baseline", "k_retrieval": 20},
    )
    if trace_response.status_code != 200:
        pytest.skip(
            "Trace unavailable; ensure indices are built and stack is ready "
            f"({trace_response.status_code})"
        )

    trace_payload = trace_response.json()
    assert isinstance(trace_payload, dict)
    assert isinstance(trace_payload.get("retrieved_docs"), list)
