from __future__ import annotations

import logging
from typing import Any

from api.app.llm.credentials import resolve_base_url
from api.app.services.recs_service import (
    INDEX_BY_MODE,
    _retrieve_candidates,
    load_llm_config,
    rank_candidates_for_mode,
    trace_retrieval_size,
)
from api.app.services.users_service import UsersService
from api.app.settings import Settings
from rag.recsys.candidate_gen import build_es_query, build_retrieval_query, build_user_context
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

        retrieval_result = _retrieve_candidates(
            settings=self.settings,
            es_client=self.es_client,
            index_name=index_name,
            retrieval_mode=llm_config.retrieval_mode,
            query_text=query_text,
            seen_movie_ids=seen_movie_ids,
            size=trace_retrieval_size(ranking_mode=llm_config.ranking_mode, k_retrieval=k_retrieval),
            strict=False,
            query_body=query_body,
        )
        candidates = retrieval_result.candidates
        logger.info(
            "trace_request phase=trace mode=%s user_id=%s index_name=%s k_retrieval=%s ranking_mode=%s retrieval_mode=%s query_text=%s",
            mode,
            user_id,
            index_name,
            k_retrieval,
            llm_config.ranking_mode,
            llm_config.retrieval_mode,
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
            victim_client = self._get_victim_client()
            rerank_base_url = _clean_optional_str(getattr(victim_client, "base_url", None))
            rerank_base_url_source: str | None = None
            if llm_config.victim.provider != "local":
                _, rerank_base_url_source = resolve_base_url(llm_config.victim.provider, self.settings)
            ranking = rank_candidates_for_mode(
                context=context,
                candidates=candidates,
                ranking_mode=llm_config.ranking_mode,
                k=max(1, min(10, len(candidates))),
                llm_client=victim_client,
                prompt_candidates=candidates,
            )
        else:
            rerank_base_url = None
            rerank_base_url_source = None
            ranking = rank_candidates_for_mode(
                context=context,
                candidates=candidates,
                ranking_mode=llm_config.ranking_mode,
                k=1,
                llm_client=None,
            )

        return {
            "ranking_mode": llm_config.ranking_mode,
            "effective_ranking_mode": ranking.effective_ranking_mode,
            "retrieval_mode": llm_config.retrieval_mode,
            "retrieval_query": query_text,
            "retrieval_query_body": query_body,
            "retrieved_docs": docs,
            "rerank_attempted": ranking.rerank_attempted,
            "rerank_candidates": ranking.rerank_candidates,
            "rerank_prompt": ranking.rerank_prompt,
            "rerank_raw_response": ranking.rerank_raw_response,
            "rerank_parsed_order": ranking.rerank_parsed_order,
            "rerank_fallback": ranking.rerank_fallback,
            "rerank_fallback_reason": ranking.rerank_fallback_reason,
            "rerank_retry_attempted": ranking.rerank_retry_attempted,
            "rerank_retry_raw_response": ranking.rerank_retry_raw_response,
            "rerank_parse_failure_stage": ranking.rerank_parse_failure_stage,
            "rerank_response_format_mode": ranking.rerank_response_format_mode,
            "rerank_json_object_key": ranking.rerank_json_object_key,
            "rerank_response_model": ranking.rerank_response_model,
            "rerank_error": ranking.rerank_error,
            "rerank_provider": llm_config.victim.provider if llm_config.ranking_mode == "llm_rerank" else None,
            "rerank_model": llm_config.victim.model if llm_config.ranking_mode == "llm_rerank" else None,
            "rerank_base_url": rerank_base_url,
            "rerank_base_url_source": rerank_base_url_source,
            "rerank_uses_victim_only": llm_config.ranking_mode == "llm_rerank",
            "attacker_provider": llm_config.attacker.provider,
            "attacker_model": llm_config.attacker.model,
            "retrieval_debug": retrieval_result.debug,
        }

    def _get_victim_client(self) -> Any | None:
        if self.llm_registry is None:
            return None

        try:
            return self.llm_registry.get_victim_client()
        except Exception:  # noqa: BLE001
            return None


def _clean_optional_str(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if cleaned == "":
        return None
    return cleaned
