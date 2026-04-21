from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from api.app.settings import Settings, get_settings
from common.schemas.api_types import DefenseSettingsRequest, DefenseSettingsResponse
from common.schemas.defense_config import DefenseConfig, load_defense_config

router = APIRouter(tags=["settings-defense"])


@router.get("/settings/defense", response_model=DefenseSettingsResponse)
def get_defense_settings(settings: Settings = Depends(get_settings)) -> DefenseSettingsResponse:
    config_path = settings.resolved_defense_config_path
    config_exists = config_path.exists() and config_path.stat().st_size > 0
    try:
        config = load_defense_config(config_path)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _build_defense_response(config=config, config_path=config_path, config_exists=config_exists)


@router.put("/settings/defense", response_model=DefenseSettingsResponse)
def put_defense_settings(
    payload: DefenseSettingsRequest,
    settings: Settings = Depends(get_settings),
) -> DefenseSettingsResponse:
    config = DefenseConfig.model_validate(payload.model_dump())
    config_path = settings.resolved_defense_config_path
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config.model_dump(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return _build_defense_response(config=config, config_path=config_path, config_exists=True)


def _build_defense_response(
    *,
    config: DefenseConfig,
    config_path: Path,
    config_exists: bool,
) -> DefenseSettingsResponse:
    config_sha256 = hashlib.sha256(config_path.read_bytes()).hexdigest() if config_exists else None
    return DefenseSettingsResponse(
        enabled=config.enabled,
        retrieval_guard_enabled=config.retrieval_guard_enabled,
        retrieval_suspicion_mode=config.retrieval_suspicion_mode,
        retrieval_penalty_weight=config.retrieval_penalty_weight,
        rerank_sanitization_enabled=config.rerank_sanitization_enabled,
        suspicious_patterns=list(config.suspicious_patterns),
        config_path=str(config_path),
        config_exists=config_exists,
        config_sha256=config_sha256,
    )
