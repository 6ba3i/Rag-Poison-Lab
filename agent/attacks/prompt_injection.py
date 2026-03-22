from __future__ import annotations

import logging

from agent.attacks.base import (
    DEFAULT_INJECTION_PAYLOAD,
    clone_docs,
    ensure_target_selected,
    resolve_keywords,
    select_poison_indices,
)

logger = logging.getLogger(__name__)


def apply_prompt_injection(
    docs: list[dict[str, object]],
    *,
    poison_fraction: float,
    payload_text: str,
    target_movie_id: int | None,
    keyword_list: list[str],
) -> list[dict[str, object]]:
    output = clone_docs(docs)
    selected = select_poison_indices(output, poison_fraction)
    logger.info(
        "prompt_injection_selected phase=attack attack_type=prompt_injection selected_before_target_enforcement=%s sample_movie_ids=%s",
        len(selected),
        _selected_movie_ids(output, selected),
    )
    selected = ensure_target_selected(
        output,
        selected_indices=selected,
        target_movie_id=target_movie_id,
    )
    logger.info(
        "prompt_injection_enforced phase=attack attack_type=prompt_injection target_movie_id=%s selected_after_target_enforcement=%s sample_movie_ids=%s",
        target_movie_id,
        len(selected),
        _selected_movie_ids(output, selected),
    )
    payload = payload_text.strip() or DEFAULT_INJECTION_PAYLOAD
    keyword_suffix = " ".join(resolve_keywords(keyword_list)).strip()
    target_id = str(target_movie_id) if target_movie_id is not None else None

    for idx in selected:
        doc = output[idx]
        doc["poison_marker"] = True
        doc["poison_payload"] = payload
        if target_id is not None and str(doc.get("movie_id", "")).strip() == target_id and keyword_suffix:
            synopsis = str(doc.get("synopsis", "") or "").strip()
            doc["synopsis"] = f"{synopsis} {keyword_suffix}".strip() if synopsis else keyword_suffix

    return output


def _selected_movie_ids(docs: list[dict[str, object]], selected: list[int], *, limit: int = 10) -> list[int]:
    output: list[int] = []
    for idx in selected[:limit]:
        try:
            output.append(int(str(docs[idx].get("movie_id", "")).strip()))
        except Exception:  # noqa: BLE001
            continue
    return output
