from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, HTTPException

from api.app.settings import Settings, get_settings
from common.schemas.api_types import AttackSettingsResponse
from common.schemas.attack_config import load_attack_config

router = APIRouter(tags=["settings-attack"])


@router.get("/settings/attack", response_model=AttackSettingsResponse)
def get_attack_settings(settings: Settings = Depends(get_settings)) -> AttackSettingsResponse:
    config_path = (settings.resolved_config_dir / "attack_config.json").resolve()
    config_exists = config_path.exists() and config_path.stat().st_size > 0

    try:
        config = load_attack_config(config_path)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

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
