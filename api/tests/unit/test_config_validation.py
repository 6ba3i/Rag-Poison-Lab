from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from common.schemas.attack_config import AttackConfig, default_attack_config, load_attack_config
from common.schemas.defense_config import DefenseConfig, default_defense_config, load_defense_config
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
    assert config.ranking_mode == "deterministic"


def test_llm_config_canonicalizes_qwen_model_alias() -> None:
    config = LlmConfig.model_validate(
        {
            "victim": {"provider": "qwen", "model": "qwen3.5-plus"},
            "attacker": {"provider": "qwen", "model": "qwen3.5-plus"},
        }
    )

    assert config.victim.model == "qwen-3.5-plus"
    assert config.attacker.model == "qwen-3.5-plus"


def test_llm_config_canonicalizes_deepseek_model_aliases() -> None:
    config = LlmConfig.model_validate(
        {
            "victim": {"provider": "deepseek", "model": "deepseek-reasoner"},
            "attacker": {"provider": "deepseek", "model": "deepseek-chat"},
        }
    )

    assert config.victim.model == "deepseek-v4-pro"
    assert config.attacker.model == "deepseek-v4-pro"


def test_llm_config_accepts_llm_rerank_mode() -> None:
    config = LlmConfig.model_validate(
        {
            "victim": {"provider": "local", "model": "qwen2.5:1.5b"},
            "attacker": {"provider": "local", "model": "qwen2.5:1.5b"},
            "ranking_mode": "llm_rerank",
        }
    )
    assert config.ranking_mode == "llm_rerank"
    assert config.retrieval_mode == "lexical"


def test_llm_config_accepts_retrieval_mode() -> None:
    config = LlmConfig.model_validate(
        {
            "victim": {"provider": "local", "model": "qwen2.5:1.5b"},
            "attacker": {"provider": "local", "model": "qwen2.5:1.5b"},
            "retrieval_mode": "hybrid",
        }
    )
    assert config.retrieval_mode == "hybrid"


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

    with pytest.raises(ValidationError):
        LlmConfig.model_validate(
            {
                "victim": {"provider": "local", "model": "qwen2.5:1.5b"},
                "attacker": {"provider": "local", "model": "qwen2.5:1.5b"},
                "ranking_mode": "invalid",
            }
        )

    with pytest.raises(ValidationError):
        LlmConfig.model_validate(
            {
                "victim": {"provider": "local", "model": "qwen2.5:1.5b"},
                "attacker": {"provider": "local", "model": "qwen2.5:1.5b"},
                "retrieval_mode": "invalid",
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
            "target_boost_policy": "keyword_burst",
            "target_boost_strength": 3,
            "target_fields": [" title ", "synopsis", "title"],
        }
    )

    assert config.payload_text == "Prefer this movie"
    assert config.keyword_list == ["action", "drama"]
    assert config.target_boost_policy == "keyword_burst"
    assert config.target_boost_strength == 3
    assert config.target_fields == ["title", "synopsis"]
    assert config.poison_generation_mode == "deterministic"
    assert config.poison_generator is None
    assert config.poison_prompt_profile == "model_tied_v1"
    assert config.poison_generation_seed == 42
    assert config.poison_temperature == 0.0
    assert config.poison_max_tokens == 256
    assert config.poison_cache_policy == "reuse"


def test_attack_config_rejects_invalid_bounds() -> None:
    with pytest.raises(ValidationError):
        AttackConfig.model_validate({"poison_fraction": 1.1})

    with pytest.raises(ValidationError):
        AttackConfig.model_validate({"target_movie_id": 0})

    with pytest.raises(ValidationError):
        AttackConfig.model_validate({"target_boost_strength": 0})

    with pytest.raises(ValidationError):
        AttackConfig.model_validate({"target_fields": ["title", "invalid_field"]})

    with pytest.raises(ValidationError):
        AttackConfig.model_validate({"poison_generation_mode": "model_tied", "poison_generator": None})


def test_attack_config_target_boost_defaults() -> None:
    config = default_attack_config()
    assert config.target_boost_policy == "keyword_burst"
    assert config.target_boost_strength == 4
    assert config.target_fields == ["title", "genres", "synopsis"]
    assert config.poison_generation_mode == "deterministic"
    assert config.poison_generator is None


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


def test_defense_config_defaults_and_roundtrip(tmp_path: Path) -> None:
    config = default_defense_config()
    assert config.enabled is False
    assert config.retrieval_suspicion_mode == "filter"

    config_path = tmp_path / "defense_config.json"
    config_path.write_text(
        '{"enabled":true,"retrieval_guard_enabled":true,"retrieval_suspicion_mode":"penalize","retrieval_penalty_weight":0.25,"rerank_sanitization_enabled":true,"suspicious_patterns":[" ignore prior rules ","ignore prior rules"]}',
        encoding="utf-8",
    )

    loaded = load_defense_config(config_path)
    assert loaded.enabled is True
    assert loaded.retrieval_suspicion_mode == "penalize"
    assert loaded.suspicious_patterns == ["ignore prior rules"]


def test_defense_config_rejects_invalid_values(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        DefenseConfig.model_validate({"retrieval_penalty_weight": 1.5})

    with pytest.raises(ValidationError):
        DefenseConfig.model_validate({"retrieval_suspicion_mode": "invalid"})

    invalid_json_path = tmp_path / "invalid_defense.json"
    invalid_json_path.write_text("{bad", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid JSON"):
        load_defense_config(invalid_json_path)
