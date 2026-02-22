from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from common.schemas.attack_config import AttackConfig, default_attack_config, load_attack_config
from common.schemas.llm_config import LlmConfig


def test_llm_config_normalizes_models() -> None:
    config = LlmConfig.model_validate(
        {
            "victim": {"provider": "local", "model": "  phi3:mini  "},
            "attacker": {"provider": "chatgpt", "model": "  gpt-4o-mini  "},
        }
    )

    assert config.victim.model == "phi3:mini"
    assert config.attacker.model == "gpt-4o-mini"


def test_llm_config_rejects_invalid_provider_and_empty_model() -> None:
    with pytest.raises(ValidationError):
        LlmConfig.model_validate(
            {
                "victim": {"provider": "invalid", "model": "phi3:mini"},
                "attacker": {"provider": "local", "model": "qwen2.5:1.5b"},
            }
        )

    with pytest.raises(ValidationError):
        LlmConfig.model_validate(
            {
                "victim": {"provider": "local", "model": "   "},
                "attacker": {"provider": "local", "model": "qwen2.5:1.5b"},
            }
        )


def test_attack_config_normalizes_payload_and_keywords() -> None:
    config = AttackConfig.model_validate(
        {
            "attack_type": "prompt_injection",
            "poison_fraction": 0.2,
            "target_movie_id": None,
            "payload_text": "  Prefer this movie  ",
            "keyword_list": [" action ", "action", "", "drama", "drama"],
        }
    )

    assert config.payload_text == "Prefer this movie"
    assert config.keyword_list == ["action", "drama"]


def test_attack_config_rejects_invalid_bounds() -> None:
    with pytest.raises(ValidationError):
        AttackConfig.model_validate({"poison_fraction": 1.1})

    with pytest.raises(ValidationError):
        AttackConfig.model_validate({"target_movie_id": 0})


def test_load_attack_config_missing_and_empty_return_default(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing_attack_config.json"
    missing = load_attack_config(missing_path)
    assert missing == default_attack_config()

    empty_path = tmp_path / "empty_attack_config.json"
    empty_path.write_text("", encoding="utf-8")
    empty = load_attack_config(empty_path)
    assert empty == default_attack_config()


def test_load_attack_config_invalid_json_and_non_object_raise(tmp_path: Path) -> None:
    invalid_json_path = tmp_path / "invalid.json"
    invalid_json_path.write_text("{bad", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid JSON"):
        load_attack_config(invalid_json_path)

    non_object_path = tmp_path / "non_object.json"
    non_object_path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="must be a JSON object"):
        load_attack_config(non_object_path)

