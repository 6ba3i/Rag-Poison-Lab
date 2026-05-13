from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from api.app.services.config_reindex_service import trigger_config_reindex
from api.app.settings import Settings, get_settings
from common.schemas.api_types import AttackSettingsRequest, AttackSettingsResponse
from common.schemas.attack_config import AttackConfig, PoisonGeneratorConfig, load_attack_config

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
    payload_data = payload.model_dump()
    generation_mode = str(payload_data.get("poison_generation_mode", "deterministic"))
    generator_provider = payload_data.pop("poison_generator_provider", None)
    generator_model = payload_data.pop("poison_generator_model", None)
    if generation_mode == "model_tied":
        if generator_provider is None or generator_model is None or str(generator_model).strip() == "":
            raise HTTPException(
                status_code=422,
                detail="poison_generator_provider and poison_generator_model are required when poison_generation_mode=model_tied",
            )
        payload_data["poison_generator"] = PoisonGeneratorConfig(
            provider=generator_provider,
            model=str(generator_model),
        ).model_dump()
    else:
        payload_data["poison_generator"] = None
    config = AttackConfig.model_validate(payload_data)
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
        poison_generation_mode=config.poison_generation_mode,
        poison_generator_provider=config.poison_generator.provider if config.poison_generator is not None else None,
        poison_generator_model=config.poison_generator.model if config.poison_generator is not None else None,
        poison_prompt_profile=config.poison_prompt_profile,
        poison_generation_seed=config.poison_generation_seed,
        poison_temperature=config.poison_temperature,
        poison_max_tokens=config.poison_max_tokens,
        poison_cache_policy=config.poison_cache_policy,
        config_path=str(config_path),
        config_exists=config_exists,
        config_sha256=config_sha256,
    )
