from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from rag.recsys.candidate_gen import CandidateDoc

BM25_WEIGHT = 0.7
GENRE_OVERLAP_WEIGHT = 0.3


@dataclass(frozen=True)
class RankedCandidate:
    candidate: CandidateDoc
    score: float


def rank_candidates(
    *,
    candidates: Sequence[CandidateDoc],
    user_top_genres: Sequence[str],
    k: int,
) -> list[RankedCandidate]:
    if k <= 0:
        return []

    bm25_components = _normalize_bm25(candidates)
    normalized_user_genres = {genre.strip().lower() for genre in user_top_genres if genre.strip()}

    ranked: list[RankedCandidate] = []
    for candidate in candidates:
        genre_overlap = _genre_overlap(candidate.genres, normalized_user_genres)
        bm25_score = bm25_components.get(candidate.movie_id, 0.0)
        final_score = (BM25_WEIGHT * bm25_score) + (GENRE_OVERLAP_WEIGHT * genre_overlap)
        ranked.append(RankedCandidate(candidate=candidate, score=round(final_score, 6)))

    ranked.sort(key=lambda item: (-item.score, item.candidate.movie_id))
    return ranked[:k]


def _normalize_bm25(candidates: Sequence[CandidateDoc]) -> dict[int, float]:
    if not candidates:
        return {}

    scores = [candidate.bm25_score for candidate in candidates]
    min_score = min(scores)
    max_score = max(scores)
    spread = max_score - min_score

    if spread <= 0.0:
        baseline = 1.0 if max_score > 0.0 else 0.0
        return {candidate.movie_id: baseline for candidate in candidates}

    return {
        candidate.movie_id: (candidate.bm25_score - min_score) / spread
        for candidate in candidates
    }


def _genre_overlap(candidate_genres: Sequence[str], user_top_genres: set[str]) -> float:
    if not user_top_genres:
        return 0.0

    candidate_set = {genre.strip().lower() for genre in candidate_genres if genre.strip()}
    if not candidate_set:
        return 0.0

    overlap = len(candidate_set.intersection(user_top_genres))
    return overlap / float(len(user_top_genres))
