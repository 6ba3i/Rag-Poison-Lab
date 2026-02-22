from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from api.app.services.trace_service import TraceService
from api.app.settings import Settings, get_es_client, get_settings
from common.schemas.api_types import TraceRequest, TraceResponse

router = APIRouter(tags=["trace"])


def get_trace_service(
    settings: Settings = Depends(get_settings),
    es_client: Any = Depends(get_es_client),
) -> TraceService:
    return TraceService(settings=settings, es_client=es_client)


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
        retrieval_query=str(trace_result["retrieval_query"]),
        retrieved_docs=trace_result["retrieved_docs"],
    )
