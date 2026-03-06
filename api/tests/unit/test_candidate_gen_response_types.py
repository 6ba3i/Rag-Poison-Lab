from __future__ import annotations

from rag.recsys.candidate_gen import search_candidates


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
