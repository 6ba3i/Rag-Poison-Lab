from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from api.app.services import results_service
from api.app.settings import Settings, get_settings
from common.schemas.api_types import RunDetailResponse, RunsListResponse

router = APIRouter(tags=["results"])


@router.get("/results/runs", response_model=RunsListResponse)
def list_runs(
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
    settings: Settings = Depends(get_settings),
) -> RunsListResponse:
    try:
        payload = results_service.list_runs(settings=settings, limit=limit, cursor=cursor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RunsListResponse.model_validate(payload)


@router.get("/results/runs/{label}", response_model=RunDetailResponse)
def get_run_detail(label: str, settings: Settings = Depends(get_settings)) -> RunDetailResponse:
    try:
        payload = results_service.get_run_detail(settings=settings, label=label)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RunDetailResponse.model_validate(payload)
