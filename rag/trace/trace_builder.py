from __future__ import annotations

from typing import Iterable

from rag.recsys.candidate_gen import CandidateDoc
from rag.trace.trace_types import TraceDocItem

SNIPPET_MAX_CHARS = 280
POISON_PAYLOAD_MAX_CHARS = 180


def build_trace_docs(*, candidates: Iterable[CandidateDoc], k: int) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []

    for candidate in candidates:
        synopsis = candidate.synopsis.strip()
        snippet = _truncate(synopsis if synopsis else candidate.title, max_chars=SNIPPET_MAX_CHARS)
        poison_payload = _truncate(candidate.poison_payload.strip(), max_chars=POISON_PAYLOAD_MAX_CHARS)
        has_poison = bool(candidate.poison_marker or poison_payload)

        trace_item = TraceDocItem(
            movie_id=candidate.movie_id,
            title=candidate.title,
            snippet=snippet,
            poison_marker=bool(candidate.poison_marker),
            poison_payload=poison_payload,
            has_poison=has_poison,
        )
        output.append(trace_item.to_dict())

        if len(output) >= k:
            break

    return output


def fallback_trace_docs_from_movies(
    *,
    movies_rows: Iterable[object],
    seen_movie_ids: set[int],
    k: int,
) -> list[dict[str, object]]:
    rows: list[tuple[int, str]] = []
    for row in movies_rows:
        if isinstance(row, dict):
            movie_id = _parse_int(row.get("movie_id"))
            title = str(row.get("title", "")).strip()
        else:
            movie_id = _parse_int(getattr(row, "movie_id", None))
            title = str(getattr(row, "title", "")).strip()

        if movie_id is None or title == "":
            continue
        rows.append((movie_id, title))

    rows.sort(key=lambda item: item[0])

    output: list[dict[str, object]] = []
    for movie_id, title in rows:
        if movie_id in seen_movie_ids:
            continue

        item = TraceDocItem(
            movie_id=movie_id,
            title=title,
            snippet=title,
            poison_marker=False,
            poison_payload="",
            has_poison=False,
        )
        output.append(item.to_dict())
        if len(output) >= k:
            break

    return output


def _truncate(text: str, *, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "..."


def _parse_int(value: object) -> int | None:
    try:
        parsed = int(str(value))
    except Exception:  # noqa: BLE001
        return None
    if parsed <= 0:
        return None
    return parsed
