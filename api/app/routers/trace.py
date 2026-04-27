from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from api.app.llm.registry import LlmRegistry
from api.app.services.trace_service import TraceService
from api.app.settings import Settings, get_es_client, get_llm_registry, get_settings
from common.schemas.api_types import TraceRequest, TraceResponse

router = APIRouter(tags=["trace"])


def get_trace_service(
    settings: Settings = Depends(get_settings),
    es_client: Any = Depends(get_es_client),
    llm_registry: LlmRegistry = Depends(get_llm_registry),
) -> TraceService:
    return TraceService(settings=settings, es_client=es_client, llm_registry=llm_registry)


@router.post("/trace", response_model=TraceResponse)
def trace(
    payload: TraceRequest,
    trace_service: TraceService = Depends(get_trace_service),
) -> TraceResponse:
    try:
        trace_result = trace_service.trace(
            user_id=payload.user_id,
            mode=payload.mode,
            k_retrieval=payload.k_retrieval,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return TraceResponse(
        user_id=payload.user_id,
        mode=payload.mode,
        ranking_mode=trace_result["ranking_mode"],
        effective_ranking_mode=trace_result.get("effective_ranking_mode"),
        retrieval_mode=trace_result.get("retrieval_mode", "lexical"),
        retrieval_query=str(trace_result["retrieval_query"]),
        retrieved_docs=trace_result["retrieved_docs"],
        rerank_attempted=trace_result.get("rerank_attempted"),
        rerank_candidates=trace_result.get("rerank_candidates"),
        rerank_prompt=trace_result.get("rerank_prompt"),
        rerank_raw_response=trace_result.get("rerank_raw_response"),
        rerank_parsed_order=trace_result.get("rerank_parsed_order"),
        rerank_fallback=trace_result.get("rerank_fallback"),
        rerank_fallback_reason=trace_result.get("rerank_fallback_reason"),
        rerank_retry_attempted=trace_result.get("rerank_retry_attempted"),
        rerank_retry_raw_response=trace_result.get("rerank_retry_raw_response"),
        rerank_parse_failure_stage=trace_result.get("rerank_parse_failure_stage"),
        rerank_response_format_mode=trace_result.get("rerank_response_format_mode"),
        rerank_json_object_key=trace_result.get("rerank_json_object_key"),
        rerank_response_model=trace_result.get("rerank_response_model"),
        rerank_error=trace_result.get("rerank_error"),
        rerank_provider=trace_result.get("rerank_provider"),
        rerank_model=trace_result.get("rerank_model"),
        rerank_base_url=trace_result.get("rerank_base_url"),
        rerank_base_url_source=trace_result.get("rerank_base_url_source"),
        rerank_uses_victim_only=bool(trace_result.get("rerank_uses_victim_only", False)),
        attacker_provider=trace_result.get("attacker_provider"),
        attacker_model=trace_result.get("attacker_model"),
        retrieval_debug=trace_result.get("retrieval_debug"),
    )
