from __future__ import annotations

from typing import Any

from api.app.services.recs_service import INDEX_BY_MODE, build_retrieval_query
from api.app.services.users_service import UsersService
from api.app.settings import Settings


class TraceService:
    def __init__(self, *, settings: Settings, es_client: Any) -> None:
        self.settings = settings
        self.es_client = es_client

    def trace(self, *, user_id: int, mode: str, k_retrieval: int) -> dict[str, Any]:
        users_service = UsersService(settings=self.settings)
        profile = users_service.get_profile(user_id)
        if profile is None:
            raise KeyError(f"Unknown user_id: {user_id}")

        history = users_service.get_history(user_id, split="all")
        seen_movie_ids = {item["movie_id"] for item in history}

        query_text = build_retrieval_query(profile)
        index_name = INDEX_BY_MODE.get(mode, "movies")
        docs = self._search(index_name=index_name, query_text=query_text, seen_movie_ids=seen_movie_ids, k=k_retrieval)

        if not docs:
            docs = self._fallback_docs(users_service=users_service, seen_movie_ids=seen_movie_ids, k=k_retrieval)

        return {
            "retrieval_query": query_text,
            "retrieved_docs": docs,
        }

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
            response = self.es_client.search(index=index_name, query=query, size=k)
        except Exception:  # noqa: BLE001
            return []

        hits_raw = response.get("hits", {}) if isinstance(response, dict) else {}
        hits = hits_raw.get("hits", []) if isinstance(hits_raw, dict) else []

        output: list[dict[str, Any]] = []
        for hit in hits:
            source = hit.get("_source", {}) if isinstance(hit, dict) else {}
            movie_id = _parse_movie_id(source.get("movie_id", hit.get("_id")))
            if movie_id is None:
                continue

            title = str(source.get("title", "")).strip()
            synopsis = str(source.get("synopsis", "")).strip()
            poison_marker = bool(source.get("poison_marker", False))
            poison_payload = str(source.get("poison_payload", "") or "")

            snippet = synopsis if synopsis else title
            if len(snippet) > 280:
                snippet = snippet[:280].rstrip() + "..."

            has_poison = poison_marker or poison_payload.strip() != ""
            output.append(
                {
                    "movie_id": movie_id,
                    "title": title,
                    "snippet": snippet,
                    "poison_marker": poison_marker,
                    "poison_payload": poison_payload,
                    "has_poison": has_poison,
                }
            )

        return output

    def _fallback_docs(self, *, users_service: UsersService, seen_movie_ids: set[int], k: int) -> list[dict[str, Any]]:
        movies = users_service.movies_df.copy()
        movies["movie_id"] = movies["movie_id"].astype("int64")
        movies = movies.sort_values("movie_id", kind="mergesort")

        docs: list[dict[str, Any]] = []
        for row in movies.itertuples(index=False):
            movie_id = int(row.movie_id)
            if movie_id in seen_movie_ids:
                continue

            title = str(row.title)
            docs.append(
                {
                    "movie_id": movie_id,
                    "title": title,
                    "snippet": title,
                    "poison_marker": False,
                    "poison_payload": "",
                    "has_poison": False,
                }
            )
            if len(docs) >= k:
                break

        return docs


def _parse_movie_id(value: object) -> int | None:
    try:
        return int(str(value))
    except Exception:  # noqa: BLE001
        return None
