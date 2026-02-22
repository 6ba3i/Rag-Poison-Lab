from __future__ import annotations

from agent.attacks.base import (
    DEFAULT_KEYWORD_LIST,
    DEFAULT_TARGETED_PAYLOAD,
    clone_docs,
    select_poison_indices,
)


def apply_targeted_promotion(
    docs: list[dict[str, object]],
    *,
    poison_fraction: float,
    target_movie_id: int | None,
    payload_text: str,
    keyword_list: list[str],
) -> list[dict[str, object]]:
    output = clone_docs(docs)
    selected = select_poison_indices(output, poison_fraction)

    if target_movie_id is not None:
        target_id = str(target_movie_id)
        target_idx = _find_movie_index(output, movie_id=target_id)
        if target_idx is None:
            raise ValueError(f"target_movie_id {target_movie_id} does not exist in source movies")
        if selected and target_idx not in selected:
            selected = [target_idx] + [idx for idx in selected if idx != target_idx][: len(selected) - 1]

    payload = payload_text.strip() or DEFAULT_TARGETED_PAYLOAD
    keywords = _resolve_keywords(keyword_list)
    keyword_suffix = " ".join(keywords).strip()

    for idx in selected:
        doc = output[idx]
        doc["poison_marker"] = True
        doc["poison_payload"] = payload
        synopsis = str(doc.get("synopsis", "") or "").strip()
        if keyword_suffix:
            doc["synopsis"] = f"{synopsis} {keyword_suffix}".strip() if synopsis else keyword_suffix

    return output


def _find_movie_index(docs: list[dict[str, object]], *, movie_id: str) -> int | None:
    for idx, doc in enumerate(docs):
        if str(doc.get("movie_id", "")).strip() == movie_id:
            return idx
    return None


def _resolve_keywords(keyword_list: list[str]) -> list[str]:
    cleaned = [token.strip() for token in keyword_list if token.strip()]
    if cleaned:
        return cleaned
    return list(DEFAULT_KEYWORD_LIST)
