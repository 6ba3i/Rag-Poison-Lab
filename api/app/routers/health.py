from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from api.app.llm.registry import LlmRegistry
from api.app.settings import get_es_client, get_llm_registry
from common.schemas.api_types import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check(
    es_client: Any = Depends(get_es_client),
    llm_registry: LlmRegistry = Depends(get_llm_registry),
) -> HealthResponse:
    try:
        es_connected = bool(es_client.ping())
    except Exception:  # noqa: BLE001
        es_connected = False

    return HealthResponse(
        status="ok",
        elasticsearch_connected=es_connected,
        ollama_connected=llm_registry.ollama_connectivity(),
    )
