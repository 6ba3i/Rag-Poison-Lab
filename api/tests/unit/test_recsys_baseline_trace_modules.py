from __future__ import annotations

from rag.recsys.candidate_gen import CandidateDoc, build_retrieval_query, build_user_context
from rag.recsys.explain import generate_explanations
from rag.recsys.ranker import rank_candidates
from rag.trace.trace_builder import build_trace_docs


def test_build_user_context_and_query_uses_train_titles_and_genres() -> None:
    profile = {
        "user_id": 7,
        "top_genres": [{"genre": "Action", "count": 3}, {"genre": "Drama", "count": 2}],
    }
    train_history = [
        {"movie_id": 10, "title": "Zulu", "rating": 4.0, "timestamp": 100},
        {"movie_id": 11, "title": "Alpha", "rating": 5.0, "timestamp": 200},
    ]

    context = build_user_context(profile=profile, train_history=train_history)
    assert context.user_id == 7
    assert context.top_genres == ("Action", "Drama")
    assert context.liked_titles == ("Alpha", "Zulu")

    query = build_retrieval_query(context)
    assert "top genres: Action, Drama" in query
    assert "liked titles: Alpha, Zulu" in query


def test_rank_candidates_deterministic_tiebreak_by_movie_id() -> None:
    candidates = [
        CandidateDoc(movie_id=4, title="Movie B", genres=("Action",), synopsis="", bm25_score=2.0),
        CandidateDoc(movie_id=3, title="Movie A", genres=("Action",), synopsis="", bm25_score=2.0),
    ]

    ranked = rank_candidates(candidates=candidates, user_top_genres=("Action",), k=2)
    assert [item.candidate.movie_id for item in ranked] == [3, 4]
    assert ranked[0].score == ranked[1].score


class _FailingLlm:
    def generate(self, **_: object) -> str:
        raise RuntimeError("unavailable")


def test_generate_explanations_falls_back_when_llm_unavailable() -> None:
    candidates = [
        CandidateDoc(movie_id=3, title="Movie A", genres=("Action",), synopsis="", bm25_score=1.0),
    ]
    ranked = rank_candidates(candidates=candidates, user_top_genres=("Action",), k=1)
    context = build_user_context(
        profile={"user_id": 1, "top_genres": [{"genre": "Action", "count": 1}]},
        train_history=[],
    )

    explanations = generate_explanations(llm_client=_FailingLlm(), context=context, ranked_candidates=ranked)
    assert 3 in explanations
    assert explanations[3].endswith(".")
    assert "Action" in explanations[3]


def test_trace_builder_truncates_and_marks_poison() -> None:
    candidates = [
        CandidateDoc(
            movie_id=5,
            title="Movie X",
            genres=("Drama",),
            synopsis="A" * 400,
            bm25_score=1.0,
            poison_marker=False,
            poison_payload="payload" * 50,
        )
    ]

    docs = build_trace_docs(candidates=candidates, k=1)
    assert len(docs) == 1
    assert docs[0]["movie_id"] == 5
    assert docs[0]["snippet"].endswith("...")
    assert docs[0]["poison_payload"].endswith("...")
    assert docs[0]["has_poison"] is True
