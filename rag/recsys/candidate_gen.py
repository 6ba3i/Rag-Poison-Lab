from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class UserPreferenceContext:
    user_id: int
    top_genres: tuple[str, ...]
    liked_movie_ids: tuple[int, ...]
    liked_titles: tuple[str, ...]


@dataclass(frozen=True)
class CandidateDoc:
    movie_id: int
    title: str
    genres: tuple[str, ...]
    synopsis: str
    bm25_score: float
    poison_marker: bool = False
    poison_payload: str = ""


def build_user_context(
    *,
    profile: dict[str, Any],
    train_history: list[dict[str, Any]],
    top_genres_k: int = 5,
    liked_titles_k: int = 5,
) -> UserPreferenceContext:
    user_id = _parse_int(profile.get("user_id"), default=0)

    top_genres: list[str] = []
    for item in profile.get("top_genres", []):
        if not isinstance(item, dict):
            continue
        genre = str(item.get("genre", "")).strip()
        if genre and genre not in top_genres:
            top_genres.append(genre)
        if len(top_genres) >= top_genres_k:
            break

    ranked_history: list[tuple[float, int, int, str]] = []
    for item in train_history:
        if not isinstance(item, dict):
            continue

        movie_id = _parse_int(item.get("movie_id"), default=-1)
        if movie_id <= 0:
            continue

        title = str(item.get("title", "")).strip()
        if title == "":
            continue

        rating = _parse_float(item.get("rating"), default=0.0)
        timestamp = _parse_int(item.get("timestamp"), default=0)
        ranked_history.append((-rating, -timestamp, movie_id, title))

    ranked_history.sort()

    liked_movie_ids: list[int] = []
    liked_titles: list[str] = []
    seen_ids: set[int] = set()
    for _, _, movie_id, title in ranked_history:
        if movie_id in seen_ids:
            continue
        seen_ids.add(movie_id)
        liked_movie_ids.append(movie_id)
        liked_titles.append(title)
        if len(liked_titles) >= liked_titles_k:
            break

    return UserPreferenceContext(
        user_id=user_id,
        top_genres=tuple(top_genres),
        liked_movie_ids=tuple(liked_movie_ids),
        liked_titles=tuple(liked_titles),
    )


def build_retrieval_query(context: UserPreferenceContext) -> str:
    parts: list[str] = []
    if context.top_genres:
        parts.append("top genres: " + ", ".join(context.top_genres))
    if context.liked_titles:
        parts.append("liked titles: " + ", ".join(context.liked_titles))
    return " ; ".join(parts) if parts else "popular movies"


def build_es_query(*, query_text: str, seen_movie_ids: set[int]) -> dict[str, Any]:
    must_not: list[dict[str, Any]] = []
    if seen_movie_ids:
        must_not.append({"terms": {"movie_id": [str(movie_id) for movie_id in sorted(seen_movie_ids)]}})

    return {
        "bool": {
            "must": [
                {
                    "multi_match": {
                        "query": query_text,
                        "fields": ["title^3", "genres^2", "synopsis"],
                        "type": "best_fields",
                    }
                }
            ],
            "must_not": must_not,
        }
    }


def search_candidates(
    *,
    es_client: Any,
    index_name: str,
    query_text: str,
    seen_movie_ids: set[int],
    size: int,
    strict: bool = False,
) -> list[CandidateDoc]:
    query = build_es_query(query_text=query_text, seen_movie_ids=seen_movie_ids)
    try:
        response = es_client.search(index=index_name, query=query, size=size)
    except Exception as exc:  # noqa: BLE001
        if strict:
            raise RuntimeError(
                f"Elasticsearch candidate retrieval failed for index '{index_name}': "
                f"{type(exc).__name__}: {exc}"
            ) from exc
        return []

    if hasattr(response, "get"):
        hits_raw = response.get("hits", {})
    else:
        hits_raw = {}

    hits: object
    if hasattr(hits_raw, "get"):
        hits = hits_raw.get("hits", [])
    else:
        hits = []

    if not isinstance(hits, list):
        return []
    return parse_hits(hits=hits, seen_movie_ids=seen_movie_ids)


def parse_hits(*, hits: Iterable[object], seen_movie_ids: set[int]) -> list[CandidateDoc]:
    output: list[CandidateDoc] = []

    for hit in hits:
        if not isinstance(hit, dict):
            continue

        source = hit.get("_source", {})
        if not isinstance(source, dict):
            source = {}

        movie_id = _parse_int(source.get("movie_id", hit.get("_id")), default=-1)
        if movie_id <= 0 or movie_id in seen_movie_ids:
            continue

        title = str(source.get("title", "")).strip()
        if title == "":
            continue

        output.append(
            CandidateDoc(
                movie_id=movie_id,
                title=title,
                genres=tuple(_normalize_genres(source.get("genres", []))),
                synopsis=str(source.get("synopsis", "") or "").strip(),
                bm25_score=_parse_float(hit.get("_score"), default=0.0),
                poison_marker=bool(source.get("poison_marker", False)),
                poison_payload=str(source.get("poison_payload", "") or "").strip(),
            )
        )

    return output


def fallback_candidates_from_movies(
    *,
    movies_rows: Iterable[object],
    seen_movie_ids: set[int],
    k: int,
) -> list[CandidateDoc]:
    output: list[CandidateDoc] = []

    parsed_rows: list[tuple[int, str, tuple[str, ...], str]] = []
    for row in movies_rows:
        if isinstance(row, dict):
            movie_id = _parse_int(row.get("movie_id"), default=-1)
            title = str(row.get("title", "")).strip()
            genres = tuple(_normalize_genres(row.get("genres", [])))
            synopsis = str(row.get("synopsis", "") or "").strip()
        else:
            movie_id = _parse_int(getattr(row, "movie_id", None), default=-1)
            title = str(getattr(row, "title", "")).strip()
            genres = tuple(_normalize_genres(getattr(row, "genres", [])))
            synopsis = str(getattr(row, "synopsis", "") or "").strip()

        if movie_id <= 0 or title == "":
            continue
        parsed_rows.append((movie_id, title, genres, synopsis))

    parsed_rows.sort(key=lambda item: item[0])

    for movie_id, title, genres, synopsis in parsed_rows:
        if movie_id in seen_movie_ids:
            continue

        output.append(
            CandidateDoc(
                movie_id=movie_id,
                title=title,
                genres=genres,
                synopsis=synopsis,
                bm25_score=0.0,
                poison_marker=False,
                poison_payload="",
            )
        )
        if len(output) >= k:
            break

    return output


def _normalize_genres(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    to_list = getattr(value, "tolist", None)
    if callable(to_list):
        raw = to_list()
        if isinstance(raw, list):
            return [str(item).strip() for item in raw if str(item).strip()]
    if isinstance(value, str):
        text = value.strip()
        if text == "":
            return []
        if text.startswith("[") and text.endswith("]"):
            text = text[1:-1]
        return [part.strip() for part in text.split("|") if part.strip()]
    return []


def _parse_int(value: object, *, default: int) -> int:
    try:
        return int(str(value))
    except Exception:  # noqa: BLE001
        return default


def _parse_float(value: object, *, default: float) -> float:
    try:
        return float(value)
    except Exception:  # noqa: BLE001
        return default
