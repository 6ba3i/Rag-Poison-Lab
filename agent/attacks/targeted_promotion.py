from __future__ import annotations

import logging

from agent.attacks.base import (
    DEFAULT_TARGETED_PAYLOAD,
    apply_target_boost,
    clone_docs,
    ensure_target_selected,
    select_poison_indices,
)
from common.schemas.attack_config import TargetBoostField, TargetBoostPolicy

logger = logging.getLogger(__name__)


def apply_targeted_promotion(
    docs: list[dict[str, object]],
    *,
    poison_fraction: float,
    target_movie_id: int | None,
    payload_text: str,
    keyword_list: list[str],
    target_boost_policy: TargetBoostPolicy,
    target_boost_strength: int,
    target_fields: list[TargetBoostField],
) -> list[dict[str, object]]:
    output = clone_docs(docs)
    selected = select_poison_indices(output, poison_fraction)
    logger.info(
        "targeted_promotion_selected phase=attack attack_type=targeted_promotion selected_before_target_enforcement=%s sample_movie_ids=%s",
        len(selected),
        _selected_movie_ids(output, selected),
    )
    selected = ensure_target_selected(
        output,
        selected_indices=selected,
        target_movie_id=target_movie_id,
    )
    logger.info(
        "targeted_promotion_enforced phase=attack attack_type=targeted_promotion target_movie_id=%s selected_after_target_enforcement=%s sample_movie_ids=%s",
        target_movie_id,
        len(selected),
        _selected_movie_ids(output, selected),
    )

    payload = payload_text.strip() or DEFAULT_TARGETED_PAYLOAD
    target_id = str(target_movie_id) if target_movie_id is not None else None

    for idx in selected:
        doc = output[idx]
        doc["poison_marker"] = True
        doc["poison_payload"] = payload
        should_boost = target_id is None or str(doc.get("movie_id", "")).strip() == target_id
        if should_boost:
            apply_target_boost(
                doc=doc,
                keyword_list=keyword_list,
                target_boost_policy=target_boost_policy,
                target_boost_strength=target_boost_strength,
                target_fields=target_fields,
            )

    return output


def _selected_movie_ids(docs: list[dict[str, object]], selected: list[int], *, limit: int = 10) -> list[int]:
    output: list[int] = []
    for idx in selected[:limit]:
        try:
            output.append(int(str(docs[idx].get("movie_id", "")).strip()))
        except Exception:  # noqa: BLE001
            continue
    return output
