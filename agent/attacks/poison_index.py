from __future__ import annotations

import logging

from agent.attacks.base import UNRELATED_SYNOPSIS_TEXT, clone_docs, select_poison_indices
from agent.attacks.prompt_injection import apply_prompt_injection
from agent.attacks.targeted_promotion import apply_targeted_promotion
from common.schemas.attack_config import AttackConfig

logger = logging.getLogger(__name__)


def apply_poisoning(docs: list[dict[str, object]], config: AttackConfig) -> list[dict[str, object]]:
    logger.info(
        "apply_poisoning_start phase=attack attack_type=%s poison_fraction=%s target_movie_id=%s total_docs=%s",
        config.attack_type,
        config.poison_fraction,
        config.target_movie_id,
        len(docs),
    )
    if config.attack_type == "targeted_promotion":
        output = apply_targeted_promotion(
            docs,
            poison_fraction=config.poison_fraction,
            target_movie_id=config.target_movie_id,
            payload_text=config.payload_text,
            keyword_list=config.keyword_list,
            target_boost_policy=config.target_boost_policy,
            target_boost_strength=config.target_boost_strength,
            target_fields=config.target_fields,
        )
        logger.info(
            "apply_poisoning_complete phase=attack attack_type=%s poisoned_docs=%s",
            config.attack_type,
            len([doc for doc in output if bool(doc.get("poison_marker", False))]),
        )
        return output

    if config.attack_type == "prompt_injection":
        output = apply_prompt_injection(
            docs,
            poison_fraction=config.poison_fraction,
            payload_text=config.payload_text,
            target_movie_id=config.target_movie_id,
            keyword_list=config.keyword_list,
        )
        logger.info(
            "apply_poisoning_complete phase=attack attack_type=%s poisoned_docs=%s",
            config.attack_type,
            len([doc for doc in output if bool(doc.get("poison_marker", False))]),
        )
        return output

    output = _apply_untargeted_degradation(docs, poison_fraction=config.poison_fraction)
    logger.info(
        "apply_poisoning_complete phase=attack attack_type=%s poisoned_docs=%s",
        config.attack_type,
        len([doc for doc in output if bool(doc.get("poison_marker", False))]),
    )
    return output


def _apply_untargeted_degradation(
    docs: list[dict[str, object]],
    *,
    poison_fraction: float,
) -> list[dict[str, object]]:
    output = clone_docs(docs)
    selected = select_poison_indices(output, poison_fraction)
    logger.info(
        "untargeted_degradation_selected phase=attack attack_type=untargeted_degradation selected_docs=%s sample_movie_ids=%s",
        len(selected),
        _selected_movie_ids(output, selected),
    )

    if not selected:
        return output

    original_genres = [_normalize_genres(output[idx].get("genres", [])) for idx in selected]
    if len(original_genres) > 1:
        rotated_genres = original_genres[1:] + original_genres[:1]
    else:
        rotated_genres = original_genres

    for idx, genres in zip(selected, rotated_genres):
        doc = output[idx]
        doc["genres"] = genres
        doc["synopsis"] = UNRELATED_SYNOPSIS_TEXT
        doc["poison_marker"] = True
        doc["poison_payload"] = ""

    return output


def _normalize_genres(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        text = value.strip()
        if text == "":
            return []
        return [part.strip() for part in text.split("|") if part.strip()]
    return []


def _selected_movie_ids(docs: list[dict[str, object]], selected: list[int], *, limit: int = 10) -> list[int]:
    output: list[int] = []
    for idx in selected[:limit]:
        try:
            output.append(int(str(docs[idx].get("movie_id", "")).strip()))
        except Exception:  # noqa: BLE001
            continue
    return output
