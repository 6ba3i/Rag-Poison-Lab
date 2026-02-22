from __future__ import annotations

import json
import re
from typing import Any, Sequence

from rag.recsys.candidate_gen import UserPreferenceContext
from rag.recsys.prompts import build_explanation_user_prompt, explanation_json_schema, explanation_system_prompt
from rag.recsys.ranker import RankedCandidate

GENERATION_TEMPERATURE = 0.0
GENERATION_MAX_TOKENS = 256


def generate_explanations(
    *,
    llm_client: Any | None,
    context: UserPreferenceContext,
    ranked_candidates: Sequence[RankedCandidate],
) -> dict[int, str]:
    if not ranked_candidates:
        return {}

    fallback = {
        item.candidate.movie_id: _template_explanation(candidate=item.candidate.title, context=context)
        for item in ranked_candidates
    }

    if llm_client is None:
        return fallback

    try:
        prompt = build_explanation_user_prompt(
            context=context,
            candidates=[item.candidate for item in ranked_candidates],
        )
        raw = llm_client.generate(
            prompt=prompt,
            system=explanation_system_prompt(),
            json_schema=explanation_json_schema(),
            temperature=GENERATION_TEMPERATURE,
            max_tokens=GENERATION_MAX_TOKENS,
        )
        parsed = _parse_llm_explanations(raw)
    except Exception:  # noqa: BLE001
        return fallback

    output: dict[int, str] = {}
    for item in ranked_candidates:
        movie_id = item.candidate.movie_id
        fallback_text = fallback[movie_id]
        output[movie_id] = _normalize_sentence(parsed.get(movie_id, fallback_text)) or fallback_text

    return output


def _parse_llm_explanations(raw: str) -> dict[int, str]:
    payload = json.loads(raw)
    items: list[object] = []

    if isinstance(payload, dict):
        raw_items = payload.get("items", [])
        if isinstance(raw_items, list):
            items = raw_items
    elif isinstance(payload, list):
        items = payload

    output: dict[int, str] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            movie_id = int(item.get("movie_id"))
        except Exception:  # noqa: BLE001
            continue

        explanation = _normalize_sentence(str(item.get("explanation", "")).strip())
        if explanation:
            output[movie_id] = explanation

    return output


def _template_explanation(*, candidate: str, context: UserPreferenceContext) -> str:
    if context.top_genres:
        return f"Recommended because it matches your interest in {context.top_genres[0]}."
    if context.liked_titles:
        return "Recommended because it is similar to movies you rated highly."
    return f"Recommended because {candidate} fits your profile."


def _normalize_sentence(text: str) -> str:
    compact = " ".join(text.split())
    if compact == "":
        return ""

    first_sentence = re.split(r"(?<=[.!?])\s+", compact, maxsplit=1)[0].strip()
    if first_sentence == "":
        return ""

    if first_sentence[-1] not in ".!?":
        first_sentence += "."
    return first_sentence
