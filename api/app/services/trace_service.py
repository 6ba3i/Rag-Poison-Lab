from __future__ import annotations

from typing import Any

from api.app.services.recs_service import INDEX_BY_MODE
from api.app.services.users_service import UsersService
from api.app.settings import Settings
from rag.recsys.candidate_gen import build_retrieval_query, build_user_context, search_candidates
from rag.trace.trace_builder import build_trace_docs, fallback_trace_docs_from_movies


class TraceService:
    def __init__(self, *, settings: Settings, es_client: Any) -> None:
        self.settings = settings
        self.es_client = es_client

    def trace(self, *, user_id: int, mode: str, k_retrieval: int) -> dict[str, Any]:
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
            size=k_retrieval,
        )

        if candidates:
            docs = build_trace_docs(candidates=candidates, k=k_retrieval)
        else:
            docs = fallback_trace_docs_from_movies(
                movies_rows=users_service.movies_df.itertuples(index=False),
                seen_movie_ids=seen_movie_ids,
                k=k_retrieval,
            )

        return {
            "retrieval_query": query_text,
            "retrieved_docs": docs,
        }
