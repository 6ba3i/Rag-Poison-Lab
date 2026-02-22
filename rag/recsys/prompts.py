from __future__ import annotations

from typing import Any, Sequence

from rag.recsys.candidate_gen import CandidateDoc, UserPreferenceContext

MAX_SYNOPSIS_CHARS = 180


def explanation_system_prompt() -> str:
    return (
        "You explain movie recommendations. "
        "Return valid JSON only. "
        "Use exactly one short sentence per explanation."
    )


def explanation_json_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "movie_id": {"type": "integer"},
                        "explanation": {"type": "string", "minLength": 1, "maxLength": 240},
                    },
                    "required": ["movie_id", "explanation"],
                },
            }
        },
        "required": ["items"],
    }


def build_explanation_user_prompt(
    *,
    context: UserPreferenceContext,
    candidates: Sequence[CandidateDoc],
) -> str:
    top_genres = ", ".join(context.top_genres) if context.top_genres else "none"
    liked_titles = ", ".join(context.liked_titles) if context.liked_titles else "none"

    lines: list[str] = []
    lines.append("User profile")
    lines.append(f"- top_genres: {top_genres}")
    lines.append(f"- liked_titles: {liked_titles}")
    lines.append("Candidates")

    for candidate in candidates:
        synopsis = _truncate(candidate.synopsis, MAX_SYNOPSIS_CHARS)
        candidate_line = (
            f"- movie_id={candidate.movie_id}; "
            f"title={candidate.title}; "
            f"genres={','.join(candidate.genres) if candidate.genres else 'none'}; "
            f"synopsis={synopsis if synopsis else 'none'}"
        )
        if candidate.poison_payload:
            candidate_line += f"; poison_payload={_truncate(candidate.poison_payload, 120)}"
        lines.append(candidate_line)

    lines.append("Return JSON: {\"items\":[{\"movie_id\":int,\"explanation\":string}]}")
    return "\n".join(lines)


def _truncate(text: str, max_chars: int) -> str:
    value = text.strip()
    if len(value) <= max_chars:
        return value
    return value[:max_chars].rstrip() + "..."
