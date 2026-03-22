from __future__ import annotations

import logging
from typing import Any

from api.app.services.recs_service import (
    INDEX_BY_MODE,
    load_llm_config,
    rank_candidates_for_mode,
    trace_retrieval_size,
)
from api.app.services.users_service import UsersService
from api.app.settings import Settings
from rag.recsys.candidate_gen import build_es_query, build_retrieval_query, build_user_context, search_candidates
from rag.trace.trace_builder import build_trace_docs, fallback_trace_docs_from_movies

logger = logging.getLogger(__name__)


class TraceService:
    def __init__(self, *, settings: Settings, es_client: Any, llm_registry: Any | None = None) -> None:
        self.settings = settings
        self.es_client = es_client
        self.llm_registry = llm_registry

    def trace(self, *, user_id: int, mode: str, k_retrieval: int) -> dict[str, Any]:
        users_service = UsersService(settings=self.settings)
        profile = users_service.get_profile(user_id)
        if profile is None:
            raise KeyError(f"Unknown user_id: {user_id}")

        llm_config = load_llm_config(settings=self.settings)

        history_all = users_service.get_history(user_id, split="all")
        history_train = users_service.get_history(user_id, split="train")
        seen_movie_ids = {item["movie_id"] for item in history_all}

        context = build_user_context(profile=profile, train_history=history_train)
        query_text = build_retrieval_query(context)
        index_name = INDEX_BY_MODE.get(mode, "movies")
        query_body = build_es_query(query_text=query_text, seen_movie_ids=seen_movie_ids)

        candidates = search_candidates(
            es_client=self.es_client,
            index_name=index_name,
            query_text=query_text,
            seen_movie_ids=seen_movie_ids,
            size=trace_retrieval_size(ranking_mode=llm_config.ranking_mode, k_retrieval=k_retrieval),
            query_body=query_body,
        )
        logger.info(
            "trace_request phase=trace mode=%s user_id=%s index_name=%s k_retrieval=%s ranking_mode=%s query_text=%s",
            mode,
            user_id,
            index_name,
            k_retrieval,
            llm_config.ranking_mode,
            query_text,
        )

        if candidates:
            docs = build_trace_docs(candidates=candidates, k=k_retrieval)
        else:
            docs = fallback_trace_docs_from_movies(
                movies_rows=users_service.movies_df.itertuples(index=False),
                seen_movie_ids=seen_movie_ids,
                k=k_retrieval,
            )

        if llm_config.ranking_mode == "llm_rerank":
            ranking = rank_candidates_for_mode(
                context=context,
                candidates=candidates,
                ranking_mode=llm_config.ranking_mode,
                k=max(1, min(10, len(candidates))),
                llm_client=self._get_victim_client(),
            )
        else:
            ranking = rank_candidates_for_mode(
                context=context,
                candidates=candidates,
                ranking_mode=llm_config.ranking_mode,
                k=1,
                llm_client=None,
            )

        return {
            "ranking_mode": llm_config.ranking_mode,
            "retrieval_query": query_text,
            "retrieval_query_body": query_body,
            "retrieved_docs": docs,
            "rerank_candidates": ranking.rerank_candidates,
            "rerank_prompt": ranking.rerank_prompt,
            "rerank_raw_response": ranking.rerank_raw_response,
            "rerank_parsed_order": ranking.rerank_parsed_order,
            "rerank_fallback": ranking.rerank_fallback,
        }

    def _get_victim_client(self) -> Any | None:
        if self.llm_registry is None:
            return None

        try:
            return self.llm_registry.get_victim_client()
        except Exception:  # noqa: BLE001
            return None
