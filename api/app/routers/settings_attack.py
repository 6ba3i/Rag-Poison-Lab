from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from api.app.services.config_reindex_service import trigger_config_reindex
from api.app.settings import Settings, get_settings
from common.schemas.api_types import AttackSettingsRequest, AttackSettingsResponse
from common.schemas.attack_config import AttackConfig, load_attack_config

router = APIRouter(tags=["settings-attack"])


@router.get("/settings/attack", response_model=AttackSettingsResponse)
def get_attack_settings(settings: Settings = Depends(get_settings)) -> AttackSettingsResponse:
    config_path = settings.resolved_attack_config_path
    config_exists = config_path.exists() and config_path.stat().st_size > 0

    try:
        config = load_attack_config(config_path)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return _build_attack_response(config=config, config_path=config_path, config_exists=config_exists)


@router.put("/settings/attack", response_model=AttackSettingsResponse)
def put_attack_settings(
    payload: AttackSettingsRequest,
    settings: Settings = Depends(get_settings),
) -> AttackSettingsResponse:
    config = AttackConfig.model_validate(payload.model_dump())
    config_path = settings.resolved_attack_config_path
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config.model_dump(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    trigger_config_reindex(settings=settings, reason="attack_config_updated")
    return _build_attack_response(config=config, config_path=config_path, config_exists=True)


def _build_attack_response(
    *,
    config: AttackConfig,
    config_path: Path,
    config_exists: bool,
) -> AttackSettingsResponse:
    config_sha256 = None
    if config_exists:
        config_sha256 = hashlib.sha256(config_path.read_bytes()).hexdigest()

    return AttackSettingsResponse(
        attack_type=config.attack_type,
        poison_fraction=config.poison_fraction,
        target_movie_id=config.target_movie_id,
        payload_text=config.payload_text,
        keyword_list=list(config.keyword_list),
        target_boost_policy=config.target_boost_policy,
        target_boost_strength=config.target_boost_strength,
        target_fields=list(config.target_fields),
        config_path=str(config_path),
        config_exists=config_exists,
        config_sha256=config_sha256,
    )
