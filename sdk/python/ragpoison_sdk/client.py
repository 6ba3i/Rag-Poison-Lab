from __future__ import annotations

from typing import Any, Iterator, Mapping
from urllib.parse import quote

import httpx
from pydantic import TypeAdapter, ValidationError

from ragpoison_sdk.errors import RagPoisonSdkError
from ragpoison_sdk.types import (
    AttackSettingsRequest,
    AttackSettingsResponse,
    DefenseSettingsRequest,
    DefenseSettingsResponse,
    ExperimentRunCompleteEvent,
    ExperimentRunFailedEvent,
    ExperimentRunLogEvent,
    ExperimentRunRequest,
    ExperimentRunResponse,
    HistorySplit,
    LlmConfig,
    RankingMode,
    RecommendationItem,
    RecommendationMode,
    RunDetailResponse,
    RunsListResponse,
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

    def set_ranking_mode(self, mode: RankingMode) -> LlmConfig:
        current = self.get_llm_settings()
        updated = current.model_copy(update={"ranking_mode": mode})
        return self.set_llm_settings(updated)

    def get_attack_settings(self) -> AttackSettingsResponse:
        payload = self._request_json("GET", "/settings/attack")
        return self._validate_model(AttackSettingsResponse, payload, operation="get_attack_settings")

    def set_attack_settings(
        self,
        config: AttackSettingsRequest | AttackSettingsResponse | dict[str, Any],
    ) -> AttackSettingsResponse:
        validated = self._validate_model(AttackSettingsRequest, config, operation="set_attack_settings.input")
        payload = self._request_json("PUT", "/settings/attack", json=validated.model_dump())
        return self._validate_model(AttackSettingsResponse, payload, operation="set_attack_settings")

    def get_defense_settings(self) -> DefenseSettingsResponse:
        payload = self._request_json("GET", "/settings/defense")
        return self._validate_model(DefenseSettingsResponse, payload, operation="get_defense_settings")

    def set_defense_settings(
        self,
        config: DefenseSettingsRequest | DefenseSettingsResponse | dict[str, Any],
    ) -> DefenseSettingsResponse:
        validated = self._validate_model(DefenseSettingsRequest, config, operation="set_defense_settings.input")
        payload = self._request_json("PUT", "/settings/defense", json=validated.model_dump())
        return self._validate_model(DefenseSettingsResponse, payload, operation="set_defense_settings")

    def run_experiment(self, payload: ExperimentRunRequest | dict[str, Any]) -> ExperimentRunResponse:
        validated = self._validate_model(ExperimentRunRequest, payload, operation="run_experiment.input")
        response = self._request_json("POST", "/experiments/run", json=validated.model_dump())
        return self._validate_model(ExperimentRunResponse, response, operation="run_experiment")

    def run_experiment_stream(
        self,
        payload: ExperimentRunRequest | dict[str, Any],
    ) -> Iterator[ExperimentRunLogEvent | ExperimentRunCompleteEvent | ExperimentRunFailedEvent]:
        validated = self._validate_model(ExperimentRunRequest, payload, operation="run_experiment_stream.input")
        url = f"{self.base_url}/experiments/run/stream"
        try:
            with httpx.stream("POST", url, json=validated.model_dump(), timeout=self.timeout) as response:
                if response.status_code >= 400:
                    detail = self._extract_error_detail(response)
                    raise RagPoisonSdkError(
                        f"Request failed ({response.status_code}): POST {url} - {detail}"
                    )
                for event_name, event_payload in self._iter_sse(response):
                    if event_name == "log":
                        yield ExperimentRunLogEvent(line=str(event_payload.get("line", "")))
                    elif event_name == "failed":
                        yield ExperimentRunFailedEvent(
                            detail=str(event_payload.get("detail", "Experiment run failed")),
                            status_code=int(event_payload.get("status_code", 500)),
                        )
                    elif event_name == "complete":
                        summary_payload = event_payload.get("summary")
                        yield ExperimentRunCompleteEvent(
                            summary=self._validate_model(
                                ExperimentRunResponse,
                                summary_payload,
                                operation="run_experiment_stream.complete",
                            )
                        )
        except RagPoisonSdkError:
            raise
        except httpx.HTTPError as exc:
            raise RagPoisonSdkError(f"Request failed: POST {url}") from exc

    def list_runs(self, limit: int = 20, cursor: str | None = None) -> RunsListResponse:
        params: dict[str, Any] = {"limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        payload = self._request_json("GET", "/results/runs", params=params)
        return self._validate_model(RunsListResponse, payload, operation="list_runs")

    def get_run_detail(self, label: str) -> RunDetailResponse:
        payload = self._request_json("GET", f"/results/runs/{quote(label, safe='')}")
        return self._validate_model(RunDetailResponse, payload, operation="get_run_detail")

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

    @staticmethod
    def _iter_sse(response: httpx.Response) -> Iterator[tuple[str, dict[str, Any]]]:
        buffer = ""
        for chunk in response.iter_text():
            buffer += chunk.replace("\r\n", "\n")
            while "\n\n" in buffer:
                frame, buffer = buffer.split("\n\n", 1)
                parsed = RagPoisonClient._parse_sse_frame(frame)
                if parsed is not None:
                    yield parsed

    @staticmethod
    def _parse_sse_frame(frame: str) -> tuple[str, dict[str, Any]] | None:
        event = "message"
        data_lines: list[str] = []
        for line in frame.split("\n"):
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].lstrip())

        if not data_lines:
            return None

        try:
            payload = TypeAdapter(dict[str, Any]).validate_json("\n".join(data_lines))
        except ValidationError as exc:
            raise RagPoisonSdkError("Invalid SSE JSON payload") from exc
        return event, payload
