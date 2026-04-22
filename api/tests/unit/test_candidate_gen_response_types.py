from __future__ import annotations

from types import SimpleNamespace

from rag.recsys.candidate_gen import fallback_candidates_from_movies, search_candidates


class _ObjectApiResponseLike:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def get(self, key: str, default: object = None) -> object:
        return self._payload.get(key, default)


class _FakeClient:
    def search(self, *, index: str, query: dict[str, object], size: int) -> _ObjectApiResponseLike:
        del index, query, size
        return _ObjectApiResponseLike(
            {
                "hits": {
                    "hits": [
                        {
                            "_id": "10",
                            "_score": 3.14,
                            "_source": {
                                "movie_id": "10",
                                "title": "Movie Ten",
                                "genres": ["Action"],
                                "synopsis": "Injected summary",
                                "poison_marker": True,
                                "poison_payload": "payload text",
                            },
                        }
                    ]
                }
            }
        )


def test_search_candidates_accepts_mapping_like_response_not_only_dict() -> None:
    candidates = search_candidates(
        es_client=_FakeClient(),
        index_name="movies",
        query_text="action",
        seen_movie_ids=set(),
        size=5,
        strict=True,
    )

    assert len(candidates) == 1
    assert candidates[0].movie_id == 10
    assert candidates[0].title == "Movie Ten"
    assert candidates[0].poison_marker is True
    assert candidates[0].poison_payload == "payload text"


def test_fallback_candidates_respect_popularity_priorities() -> None:
    rows = [
        SimpleNamespace(movie_id=11, title="Movie 11", genres=["Drama"], synopsis=""),
        SimpleNamespace(movie_id=12, title="Movie 12", genres=["Action"], synopsis=""),
        SimpleNamespace(movie_id=13, title="Movie 13", genres=["Comedy"], synopsis=""),
    ]

    fallback = fallback_candidates_from_movies(
        movies_rows=rows,
        seen_movie_ids=set(),
        k=3,
        popularity_priorities={
            11: (3, 4.3),
            12: (6, 3.0),
            13: (6, 4.8),
        },
    )

    assert [item.movie_id for item in fallback] == [13, 12, 11]


def test_fallback_candidates_default_to_movie_id_order_without_priorities() -> None:
    rows = [
        SimpleNamespace(movie_id=3, title="Movie 3", genres=["Drama"], synopsis=""),
        SimpleNamespace(movie_id=1, title="Movie 1", genres=["Action"], synopsis=""),
        SimpleNamespace(movie_id=2, title="Movie 2", genres=["Comedy"], synopsis=""),
    ]

    fallback = fallback_candidates_from_movies(
        movies_rows=rows,
        seen_movie_ids=set(),
        k=3,
    )

    assert [item.movie_id for item in fallback] == [1, 2, 3]
