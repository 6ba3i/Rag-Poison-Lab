from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from api.app.services.recs_service import RecsService
from api.app.settings import Settings, get_es_client, get_settings
from common.schemas.api_types import RecommendationItem, RecommendationsRequest

router = APIRouter(tags=["recommendations"])


def get_recs_service(
    settings: Settings = Depends(get_settings),
    es_client: Any = Depends(get_es_client),
) -> RecsService:
    return RecsService(settings=settings, es_client=es_client)


@router.post("/recommendations", response_model=list[RecommendationItem])
def recommendations(
    payload: RecommendationsRequest,
    recs_service: RecsService = Depends(get_recs_service),
) -> list[RecommendationItem]:
    try:
        items = recs_service.recommend(user_id=payload.user_id, mode=payload.mode, k=payload.k)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return [RecommendationItem.model_validate(item) for item in items]
