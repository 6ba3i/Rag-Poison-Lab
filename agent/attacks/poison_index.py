from __future__ import annotations

from agent.attacks.base import UNRELATED_SYNOPSIS_TEXT, clone_docs, select_poison_indices
from agent.attacks.prompt_injection import apply_prompt_injection
from agent.attacks.targeted_promotion import apply_targeted_promotion
from common.schemas.attack_config import AttackConfig


def apply_poisoning(docs: list[dict[str, object]], config: AttackConfig) -> list[dict[str, object]]:
    if config.attack_type == "targeted_promotion":
        return apply_targeted_promotion(
            docs,
            poison_fraction=config.poison_fraction,
            target_movie_id=config.target_movie_id,
            payload_text=config.payload_text,
            keyword_list=config.keyword_list,
        )

    if config.attack_type == "prompt_injection":
        return apply_prompt_injection(
            docs,
            poison_fraction=config.poison_fraction,
            payload_text=config.payload_text,
        )

    return _apply_untargeted_degradation(docs, poison_fraction=config.poison_fraction)


def _apply_untargeted_degradation(
    docs: list[dict[str, object]],
    *,
    poison_fraction: float,
) -> list[dict[str, object]]:
    output = clone_docs(docs)
    selected = select_poison_indices(output, poison_fraction)

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
