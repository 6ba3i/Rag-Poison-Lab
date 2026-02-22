from __future__ import annotations

from typing import Any

import httpx
import pytest

from ragpoison_sdk import RagPoisonClient, RagPoisonSdkError


def _json_response(method: str, url: str, status_code: int, payload: Any) -> httpx.Response:
    request = httpx.Request(method, url)
    return httpx.Response(status_code=status_code, json=payload, request=request)


def test_list_users_normalizes_base_url_and_validates_models(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    def fake_request(
        *,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        timeout: float,
    ) -> httpx.Response:
        calls.append({"method": method, "url": url, "params": params, "json": json, "timeout": timeout})
        return _json_response(
            method,
            url,
            200,
            [{"user_id": 1, "rating_count": 10, "mean_rating": 4.2, "unexpected": "ignored"}],
        )

    monkeypatch.setattr(httpx, "request", fake_request)

    client = RagPoisonClient("http://localhost:8000")
    users = client.list_users(q="1", limit=25)

    assert len(users) == 1
    assert users[0].user_id == 1
    assert users[0].rating_count == 10
    assert calls == [
        {
            "method": "GET",
            "url": "http://localhost:8000/api/users",
            "params": {"q": "1", "limit": 25},
            "json": None,
            "timeout": 10.0,
        }
    ]


def test_get_profile_and_history_use_expected_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    queued = [
        {
            "user_id": 9,
            "rating_count": 2,
            "mean_rating": 3.5,
            "top_genres": [{"genre": "Drama", "count": 2}],
            "top_rated_movie_ids": [30],
            "recent_movie_ids": [30, 20],
        },
        [
            {
                "movie_id": 30,
                "title": "Movie",
                "rating": 4.0,
                "timestamp": 123,
                "genres": ["Drama"],
                "split": "train",
            }
        ],
    ]

    def fake_request(
        *,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        timeout: float,
    ) -> httpx.Response:
        calls.append({"method": method, "url": url, "params": params, "json": json, "timeout": timeout})
        payload = queued.pop(0)
        return _json_response(method, url, 200, payload)

    monkeypatch.setattr(httpx, "request", fake_request)

    client = RagPoisonClient("http://localhost:8000/api/")
    profile = client.get_profile(9)
    history = client.get_history(9, split="train")

    assert profile.user_id == 9
    assert history[0].movie_id == 30
    assert calls[0]["url"] == "http://localhost:8000/api/users/9/profile"
    assert calls[1]["url"] == "http://localhost:8000/api/users/9/history"
    assert calls[1]["params"] == {"split": "train"}


def test_recommend_and_trace_send_expected_payloads(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    queued = [
        [
            {
                "movie_id": 3,
                "title": "Gamma",
                "genres": ["Action"],
                "score": 0.9,
                "explanation": "Because you liked action movies.",
            }
        ],
        {
            "user_id": 1,
            "mode": "attacked",
            "retrieval_query": "top genres: Action",
            "retrieved_docs": [
                {
                    "movie_id": 4,
                    "title": "Delta",
                    "snippet": "text",
                    "poison_marker": True,
                    "poison_payload": "payload",
                    "has_poison": True,
                }
            ],
        },
    ]

    def fake_request(
        *,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        timeout: float,
    ) -> httpx.Response:
        calls.append({"method": method, "url": url, "params": params, "json": json, "timeout": timeout})
        payload = queued.pop(0)
        return _json_response(method, url, 200, payload)

    monkeypatch.setattr(httpx, "request", fake_request)

    client = RagPoisonClient("http://localhost:8000")
    recs = client.recommend(user_id=1, mode="baseline", k=5)
    trace = client.trace(user_id=1, mode="attacked", k_retrieval=15)

    assert recs[0].movie_id == 3
    assert trace.mode == "attacked"
    assert calls[0]["url"] == "http://localhost:8000/api/recommendations"
    assert calls[0]["json"] == {"user_id": 1, "mode": "baseline", "k": 5}
    assert calls[1]["url"] == "http://localhost:8000/api/trace"
    assert calls[1]["json"] == {"user_id": 1, "mode": "attacked", "k_retrieval": 15}


def test_get_and_set_llm_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    queued = [
        {
            "victim": {"provider": "local", "model": "qwen2.5:1.5b"},
            "attacker": {"provider": "local", "model": "qwen2.5:1.5b"},
        },
        {
            "victim": {"provider": "local", "model": "phi3:mini"},
            "attacker": {"provider": "local", "model": "qwen2.5:1.5b"},
        },
    ]

    def fake_request(
        *,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        timeout: float,
    ) -> httpx.Response:
        calls.append({"method": method, "url": url, "params": params, "json": json, "timeout": timeout})
        payload = queued.pop(0)
        return _json_response(method, url, 200, payload)

    monkeypatch.setattr(httpx, "request", fake_request)

    client = RagPoisonClient("http://localhost:8000")
    current = client.get_llm_settings()
    updated = client.set_llm_settings(
        {
            "victim": {"provider": "local", "model": "phi3:mini"},
            "attacker": {"provider": "local", "model": "qwen2.5:1.5b"},
        }
    )

    assert current.victim.provider == "local"
    assert updated.victim.model == "phi3:mini"
    assert calls[0]["method"] == "GET"
    assert calls[1]["method"] == "PUT"
    assert calls[1]["json"] == {
        "victim": {"provider": "local", "model": "phi3:mini"},
        "attacker": {"provider": "local", "model": "qwen2.5:1.5b"},
    }


def test_http_error_raises_sdk_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_request(
        *,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        timeout: float,
    ) -> httpx.Response:
        return _json_response(method, url, 404, {"detail": "User 999 not found"})

    monkeypatch.setattr(httpx, "request", fake_request)
    client = RagPoisonClient("http://localhost:8000")

    with pytest.raises(RagPoisonSdkError, match="User 999 not found"):
        client.get_profile(999)


def test_validation_error_raises_sdk_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_request(
        *,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        timeout: float,
    ) -> httpx.Response:
        return _json_response(method, url, 200, [{"user_id": "bad"}])

    monkeypatch.setattr(httpx, "request", fake_request)
    client = RagPoisonClient("http://localhost:8000")

    with pytest.raises(RagPoisonSdkError, match="Response validation failed"):
        client.list_users()
