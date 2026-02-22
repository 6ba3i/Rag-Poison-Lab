from __future__ import annotations

from typing import Any, Mapping

import httpx
from pydantic import TypeAdapter, ValidationError

from ragpoison_sdk.errors import RagPoisonSdkError
from ragpoison_sdk.types import (
    HistorySplit,
    LlmConfig,
    RecommendationItem,
    RecommendationMode,
    TraceResponse,
    UserHistoryItem,
    UserProfile,
    UserSummary,
)

_USER_SUMMARY_LIST_ADAPTER = TypeAdapter(list[UserSummary])
_USER_HISTORY_ITEM_LIST_ADAPTER = TypeAdapter(list[UserHistoryItem])
_RECOMMENDATION_ITEM_LIST_ADAPTER = TypeAdapter(list[RecommendationItem])


class RagPoisonClient:
    """Typed client for the RAGPoison API."""

    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        normalized_base = base_url.strip().rstrip("/")
        self.base_url = normalized_base if normalized_base.endswith("/api") else f"{normalized_base}/api"
        self.timeout = timeout

    def list_users(self, q: str = "", limit: int = 50) -> list[UserSummary]:
        payload = self._request_json("GET", "/users", params={"q": q, "limit": limit})
        return self._validate_model_list(_USER_SUMMARY_LIST_ADAPTER, payload, operation="list_users")

    def get_profile(self, user_id: int) -> UserProfile:
        payload = self._request_json("GET", f"/users/{user_id}/profile")
        return self._validate_model(UserProfile, payload, operation="get_profile")

    def get_history(self, user_id: int, split: HistorySplit = "all") -> list[UserHistoryItem]:
        payload = self._request_json("GET", f"/users/{user_id}/history", params={"split": split})
        return self._validate_model_list(_USER_HISTORY_ITEM_LIST_ADAPTER, payload, operation="get_history")

    def recommend(
        self,
        user_id: int,
        mode: RecommendationMode = "baseline",
        k: int = 10,
    ) -> list[RecommendationItem]:
        payload = self._request_json(
            "POST",
            "/recommendations",
            json={"user_id": user_id, "mode": mode, "k": k},
        )
        return self._validate_model_list(_RECOMMENDATION_ITEM_LIST_ADAPTER, payload, operation="recommend")

    def trace(
        self,
        user_id: int,
        mode: RecommendationMode = "baseline",
        k_retrieval: int = 20,
    ) -> TraceResponse:
        payload = self._request_json(
            "POST",
            "/trace",
            json={"user_id": user_id, "mode": mode, "k_retrieval": k_retrieval},
        )
        return self._validate_model(TraceResponse, payload, operation="trace")

    def get_llm_settings(self) -> LlmConfig:
        payload = self._request_json("GET", "/settings/llm")
        return self._validate_model(LlmConfig, payload, operation="get_llm_settings")

    def set_llm_settings(self, config: LlmConfig | dict[str, Any]) -> LlmConfig:
        validated = self._validate_model(LlmConfig, config, operation="set_llm_settings.input")
        payload = self._request_json("PUT", "/settings/llm", json=validated.model_dump())
        return self._validate_model(LlmConfig, payload, operation="set_llm_settings")

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Mapping[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            response = httpx.request(
                method=method,
                url=url,
                params=params,
                json=json,
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise RagPoisonSdkError(f"Request failed: {method} {url}") from exc

        if response.status_code >= 400:
            detail = self._extract_error_detail(response)
            raise RagPoisonSdkError(f"Request failed ({response.status_code}): {method} {url} - {detail}")

        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            raise RagPoisonSdkError(f"Expected JSON response for {method} {url}, got content-type: {content_type!r}")

        try:
            return response.json()
        except ValueError as exc:
            raise RagPoisonSdkError(f"Invalid JSON response for {method} {url}") from exc

    @staticmethod
    def _extract_error_detail(response: httpx.Response) -> str:
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                payload = response.json()
            except ValueError:
                return response.text or response.reason_phrase or "Request failed"

            if isinstance(payload, dict) and "detail" in payload:
                return str(payload["detail"])
            return str(payload)

        return response.text or response.reason_phrase or "Request failed"

    @staticmethod
    def _validate_model(model: type[Any], payload: Any, *, operation: str) -> Any:
        try:
            return model.model_validate(payload)
        except ValidationError as exc:
            raise RagPoisonSdkError(f"Response validation failed for {operation}") from exc

    @staticmethod
    def _validate_model_list(adapter: TypeAdapter[Any], payload: Any, *, operation: str) -> Any:
        try:
            return adapter.validate_python(payload)
        except ValidationError as exc:
            raise RagPoisonSdkError(f"Response validation failed for {operation}") from exc
