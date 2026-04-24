from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException

from api.app.llm.registry import LlmRegistry
from api.app.services.config_reindex_service import trigger_config_reindex
from api.app.settings import Settings, get_llm_registry, get_settings
from common.schemas.api_types import LlmSettingsOptionsResponse
from common.schemas.llm_config import LlmConfig, default_llm_config

router = APIRouter(tags=["settings-llm"])


@router.get("/settings/llm", response_model=LlmConfig)
def get_llm_settings(settings: Settings = Depends(get_settings)) -> LlmConfig:
    config = _load_or_initialize_llm_config(settings)
    return config


@router.put("/settings/llm", response_model=LlmConfig)
def put_llm_settings(
    config: LlmConfig,
    settings: Settings = Depends(get_settings),
    llm_registry: LlmRegistry = Depends(get_llm_registry),
) -> LlmConfig:
    provider_options = {option.provider: option for option in llm_registry.list_provider_options()}

    for role_name, role in (("victim", config.victim), ("attacker", config.attacker)):
        option = provider_options.get(role.provider)
        if option is None:
            raise HTTPException(status_code=400, detail=f"Unknown provider for {role_name}: {role.provider}")
        if role.provider != "local" and not option.available:
            raise HTTPException(
                status_code=400,
                detail=f"Provider '{role.provider}' for {role_name} is unavailable because its API key env var is missing",
            )

    _save_llm_config(settings, config)
    trigger_config_reindex(settings=settings, reason="llm_config_updated")
    return config


@router.get("/settings/llm/options", response_model=LlmSettingsOptionsResponse)
def get_llm_options(llm_registry: LlmRegistry = Depends(get_llm_registry)) -> LlmSettingsOptionsResponse:
    return LlmSettingsOptionsResponse(providers=llm_registry.list_provider_options())


def _load_or_initialize_llm_config(settings: Settings) -> LlmConfig:
    path = settings.resolved_llm_config_path
    if not path.exists() or path.stat().st_size == 0:
        config = default_llm_config()
        _save_llm_config(settings, config)
        return config

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        config = LlmConfig.model_validate(payload)
        return config
    except Exception:  # noqa: BLE001
        config = default_llm_config()
        _save_llm_config(settings, config)
        return config


def _save_llm_config(settings: Settings, config: LlmConfig) -> None:
    path = settings.resolved_llm_config_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config.model_dump(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
