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
        retrieval_debug=trace_result.get("retrieval_debug"),
    )
