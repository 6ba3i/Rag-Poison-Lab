from __future__ import annotations

from typing import Any

from api.app.settings import Settings
from api.app.services.users_service import UsersService
from rag.recsys.candidate_gen import (
    build_retrieval_query,
    build_user_context,
    fallback_candidates_from_movies,
    search_candidates,
)
from rag.recsys.explain import generate_explanations
from rag.recsys.ranker import rank_candidates

INDEX_BY_MODE = {
    "baseline": "movies",
    "attacked": "movies_poisoned",
}


class RecsService:
    def __init__(
        self,
        *,
        settings: Settings,
        es_client: Any,
        llm_registry: Any | None = None,
    ) -> None:
        self.settings = settings
        self.es_client = es_client
        self.llm_registry = llm_registry

    def recommend(self, *, user_id: int, mode: str, k: int) -> list[dict[str, Any]]:
        users_service = UsersService(settings=self.settings)
        profile = users_service.get_profile(user_id)
        if profile is None:
            raise KeyError(f"Unknown user_id: {user_id}")

        history_all = users_service.get_history(user_id, split="all")
        history_train = users_service.get_history(user_id, split="train")
        seen_movie_ids = {item["movie_id"] for item in history_all}

        context = build_user_context(profile=profile, train_history=history_train)
        query_text = build_retrieval_query(context)
        index_name = INDEX_BY_MODE.get(mode, "movies")

        candidates = search_candidates(
            es_client=self.es_client,
            index_name=index_name,
            query_text=query_text,
            seen_movie_ids=seen_movie_ids,
            size=max(k * 4, k + 10),
        )

        if len(candidates) < k:
            fallback = fallback_candidates_from_movies(
                movies_rows=users_service.movies_df.itertuples(index=False),
                seen_movie_ids=seen_movie_ids,
                k=k,
            )
            existing_ids = {candidate.movie_id for candidate in candidates}
            for candidate in fallback:
                if candidate.movie_id in existing_ids:
                    continue
                candidates.append(candidate)
                existing_ids.add(candidate.movie_id)
                if len(candidates) >= k:
                    break

        ranked = rank_candidates(candidates=candidates, user_top_genres=context.top_genres, k=k)
        explanations = generate_explanations(
            llm_client=self._get_victim_client(),
            context=context,
            ranked_candidates=ranked,
        )

        output: list[dict[str, Any]] = []
        for item in ranked:
            movie_id = item.candidate.movie_id
            output.append(
                {
                    "movie_id": movie_id,
                    "title": item.candidate.title,
                    "genres": list(item.candidate.genres),
                    "score": float(item.score),
                    "explanation": explanations.get(movie_id, "Recommended from deterministic ranking."),
                }
            )

        return output

    def _get_victim_client(self) -> Any | None:
        if self.llm_registry is None:
            return None

        try:
            return self.llm_registry.get_victim_client()
        except Exception:  # noqa: BLE001
            return None
