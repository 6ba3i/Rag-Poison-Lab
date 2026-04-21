from __future__ import annotations

from collections import defaultdict
from typing import Any

from rag.recsys.candidate_gen import CandidateDoc, search_candidates
from rag.retrieval.mappings import dense_corpus_rows
from rag.retrieval.query_builder import cosine_similarity, hashed_dense_vector
from rag.retrieval.schemas import RetrievalResult

HYBRID_FETCH_MULTIPLIER = 3
RRF_K = 60.0


def retrieve_lexical(
    *,
    es_client: Any,
    index_name: str,
    query_text: str,
    seen_movie_ids: set[int],
    size: int,
    strict: bool,
    query_body: dict[str, Any],
) -> RetrievalResult:
    candidates = search_candidates(
        es_client=es_client,
        index_name=index_name,
        query_text=query_text,
        seen_movie_ids=seen_movie_ids,
        size=size,
        strict=strict,
        query_body=query_body,
    )
    return RetrievalResult(
        candidates=candidates,
        debug={
            "retrieval_mode": "lexical",
            "query_body": query_body,
            "candidate_count": len(candidates),
        },
    )


def retrieve_dense(
    *,
    processed_dir: Any,
    index_name: str,
    query_text: str,
    seen_movie_ids: set[int],
    size: int,
) -> RetrievalResult:
    corpus = dense_corpus_rows(processed_dir=processed_dir, index_name=index_name)
    query_vector = hashed_dense_vector(query_text)
    ranked: list[CandidateDoc] = []
    scored_rows: list[dict[str, Any]] = []

    for row in corpus:
        movie_id = int(row["movie_id"])
        if movie_id in seen_movie_ids:
            continue
        score = cosine_similarity(query_vector, row["vector"])
        if score <= 0.0:
            continue
        scored_rows.append(
            {
                "movie_id": movie_id,
                "title": str(row["title"]),
                "score": score,
                "genres": list(row["genres"]),
                "synopsis": str(row["synopsis"]),
                "poison_marker": bool(row["poison_marker"]),
                "poison_payload": str(row["poison_payload"]),
            }
        )

    scored_rows.sort(key=lambda item: (-float(item["score"]), int(item["movie_id"])))
    for item in scored_rows[:size]:
        ranked.append(
            CandidateDoc(
                movie_id=int(item["movie_id"]),
                title=str(item["title"]),
                genres=tuple(str(genre) for genre in item["genres"]),
                synopsis=str(item["synopsis"]),
                bm25_score=round(float(item["score"]), 6),
                poison_marker=bool(item["poison_marker"]),
                poison_payload=str(item["poison_payload"]),
            )
        )

    return RetrievalResult(
        candidates=ranked,
        debug={
            "retrieval_mode": "dense",
            "candidate_count": len(ranked),
            "dense_scores": {
                str(item["movie_id"]): round(float(item["score"]), 6)
                for item in scored_rows[:size]
            },
        },
    )


def retrieve_hybrid(
    *,
    es_client: Any,
    processed_dir: Any,
    index_name: str,
    query_text: str,
    seen_movie_ids: set[int],
    size: int,
    strict: bool,
    query_body: dict[str, Any],
) -> RetrievalResult:
    lexical = retrieve_lexical(
        es_client=es_client,
        index_name=index_name,
        query_text=query_text,
        seen_movie_ids=seen_movie_ids,
        size=size * HYBRID_FETCH_MULTIPLIER,
        strict=strict,
        query_body=query_body,
    )
    dense = retrieve_dense(
        processed_dir=processed_dir,
        index_name=index_name,
        query_text=query_text,
        seen_movie_ids=seen_movie_ids,
        size=size * HYBRID_FETCH_MULTIPLIER,
    )

    scores: dict[int, float] = defaultdict(float)
    candidates_by_id: dict[int, CandidateDoc] = {}
    breakdown: dict[int, dict[str, float | int]] = defaultdict(dict)

    for rank, candidate in enumerate(lexical.candidates, start=1):
        scores[candidate.movie_id] += 1.0 / (RRF_K + float(rank))
        candidates_by_id[candidate.movie_id] = candidate
        breakdown[candidate.movie_id]["lexical_rank"] = rank
        breakdown[candidate.movie_id]["lexical_score"] = round(float(candidate.bm25_score), 6)

    for rank, candidate in enumerate(dense.candidates, start=1):
        scores[candidate.movie_id] += 1.0 / (RRF_K + float(rank))
        candidates_by_id.setdefault(candidate.movie_id, candidate)
        breakdown[candidate.movie_id]["dense_rank"] = rank
        breakdown[candidate.movie_id]["dense_score"] = round(float(candidate.bm25_score), 6)

    fused: list[CandidateDoc] = []
    ordered_ids = sorted(scores.keys(), key=lambda movie_id: (-scores[movie_id], movie_id))
    for movie_id in ordered_ids[:size]:
        candidate = candidates_by_id[movie_id]
        fused.append(
            CandidateDoc(
                movie_id=candidate.movie_id,
                title=candidate.title,
                genres=candidate.genres,
                synopsis=candidate.synopsis,
                bm25_score=round(float(scores[movie_id]), 6),
                poison_marker=candidate.poison_marker,
                poison_payload=candidate.poison_payload,
            )
        )

    return RetrievalResult(
        candidates=fused,
        debug={
            "retrieval_mode": "hybrid",
            "candidate_count": len(fused),
            "hybrid_breakdown": {str(movie_id): breakdown[movie_id] for movie_id in ordered_ids[:size]},
        },
    )
