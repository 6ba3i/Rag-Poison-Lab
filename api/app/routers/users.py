from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from api.app.services.users_service import UsersService
from api.app.settings import Settings, get_settings
from common.schemas.api_types import UserHistoryItem, UserProfile, UserSummary

router = APIRouter(tags=["users"])


def get_users_service(settings: Settings = Depends(get_settings)) -> UsersService:
    return UsersService(settings=settings)


@router.get("/users", response_model=list[UserSummary])
def list_users(
    q: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=500),
    users_service: UsersService = Depends(get_users_service),
) -> list[UserSummary]:
    try:
        return [UserSummary.model_validate(item) for item in users_service.list_users(q=q, limit=limit)]
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/users/{user_id}/profile", response_model=UserProfile)
def get_user_profile(
    user_id: int,
    users_service: UsersService = Depends(get_users_service),
) -> UserProfile:
    try:
        profile = users_service.get_profile(user_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if profile is None:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    return UserProfile.model_validate(profile)


@router.get("/users/{user_id}/history", response_model=list[UserHistoryItem])
def get_user_history(
    user_id: int,
    split: Literal["train", "all"] = Query(default="all"),
    users_service: UsersService = Depends(get_users_service),
) -> list[UserHistoryItem]:
    try:
        profile = users_service.get_profile(user_id)
        if profile is None:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")

        items = users_service.get_history(user_id, split=split)
        return [UserHistoryItem.model_validate(item) for item in items]
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
