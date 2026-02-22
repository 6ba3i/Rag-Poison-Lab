from __future__ import annotations

from typing import Any

from api.app.settings import Settings
from api.app.services.users_service import UsersService

INDEX_BY_MODE = {
    "baseline": "movies",
    "attacked": "movies_poisoned",
}


class RecsService:
    def __init__(self, *, settings: Settings, es_client: Any) -> None:
        self.settings = settings
        self.es_client = es_client

    def recommend(self, *, user_id: int, mode: str, k: int) -> list[dict[str, Any]]:
        users_service = UsersService(settings=self.settings)
        profile = users_service.get_profile(user_id)
        if profile is None:
            raise KeyError(f"Unknown user_id: {user_id}")

        history = users_service.get_history(user_id, split="all")
        seen_movie_ids = {item["movie_id"] for item in history}

        query_text = build_retrieval_query(profile)
        index_name = INDEX_BY_MODE.get(mode, "movies")
        results = self._search(index_name=index_name, query_text=query_text, seen_movie_ids=seen_movie_ids, k=k)

        if len(results) < k:
            fallback = self._fallback_movies(users_service=users_service, seen_movie_ids=seen_movie_ids, k=k)
            seen = {item["movie_id"] for item in results}
            for item in fallback:
                if item["movie_id"] in seen:
                    continue
                results.append(item)
                seen.add(item["movie_id"])
                if len(results) >= k:
                    break

        return results[:k]

    def _search(self, *, index_name: str, query_text: str, seen_movie_ids: set[int], k: int) -> list[dict[str, Any]]:
        must_not: list[dict[str, Any]] = []
        if seen_movie_ids:
            must_not.append({"terms": {"movie_id": [str(movie_id) for movie_id in sorted(seen_movie_ids)]}})

        query = {
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

        try:
            response = self.es_client.search(index=index_name, query=query, size=max(k * 4, k + 10))
        except Exception:  # noqa: BLE001
            return []

        hits_raw = response.get("hits", {}) if isinstance(response, dict) else {}
        hits = hits_raw.get("hits", []) if isinstance(hits_raw, dict) else []
        parsed: list[dict[str, Any]] = []

        for hit in hits:
            source = hit.get("_source", {}) if isinstance(hit, dict) else {}
            movie_id = _parse_movie_id(source.get("movie_id", hit.get("_id")))
            if movie_id is None:
                continue
            if movie_id in seen_movie_ids:
                continue

            title = str(source.get("title", "")).strip()
            if title == "":
                continue

            parsed.append(
                {
                    "movie_id": movie_id,
                    "title": title,
                    "score": float(hit.get("_score", 0.0)),
                    "explanation": "Recommended because it matches your profile and similar liked titles.",
                }
            )

        parsed.sort(key=lambda item: (-item["score"], item["movie_id"]))
        return parsed[:k]

    def _fallback_movies(self, *, users_service: UsersService, seen_movie_ids: set[int], k: int) -> list[dict[str, Any]]:
        movies = users_service.movies_df.copy()
        movies["movie_id"] = movies["movie_id"].astype("int64")
        movies = movies.sort_values("movie_id", kind="mergesort")

        output: list[dict[str, Any]] = []
        for row in movies.itertuples(index=False):
            movie_id = int(row.movie_id)
            if movie_id in seen_movie_ids:
                continue
            output.append(
                {
                    "movie_id": movie_id,
                    "title": str(row.title),
                    "score": 0.0,
                    "explanation": "Recommended from deterministic fallback ranking.",
                }
            )
            if len(output) >= k:
                break
        return output


def build_retrieval_query(profile: dict[str, Any]) -> str:
    top_genres = [str(item.get("genre", "")).strip() for item in profile.get("top_genres", []) if isinstance(item, dict)]
    top_genres = [genre for genre in top_genres if genre]
    top_movies = [str(movie_id) for movie_id in profile.get("top_rated_movie_ids", [])[:5]]

    parts: list[str] = []
    if top_genres:
        parts.append("preferred genres: " + ", ".join(top_genres[:5]))
    if top_movies:
        parts.append("liked movie ids: " + ", ".join(top_movies))

    return " ; ".join(parts) if parts else "popular movies"


def _parse_movie_id(value: object) -> int | None:
    try:
        return int(str(value))
    except Exception:  # noqa: BLE001
        return None
