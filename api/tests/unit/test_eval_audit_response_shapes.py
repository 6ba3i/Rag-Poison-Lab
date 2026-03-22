from __future__ import annotations

from types import SimpleNamespace

from api.app.eval import audit as eval_audit
from api.app.eval import runner as eval_runner
from common.schemas.attack_config import AttackConfig


class ObjectResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def get(self, key: str, default=None):  # noqa: ANN001
        return self.payload.get(key, default)


class FakeUsersService:
    def get_profile(self, user_id: int):
        return {
            "user_id": user_id,
            "top_genres": [{"genre": "Drama", "count": 2}, {"genre": "Comedy", "count": 1}],
        }

    def get_history(self, user_id: int, split: str):  # noqa: ARG002
        return [
            {
                "movie_id": 11,
                "title": "Alpha (1990)",
                "rating": 5.0,
                "timestamp": 10,
            },
            {
                "movie_id": 12,
                "title": "Beta (1991)",
                "rating": 4.0,
                "timestamp": 9,
            },
        ]


class FakeRecsService:
    def recommend_with_debug(
        self,
        *,
        user_id: int,
        mode: str,
        k: int,
        seen_history_split: str,
        strict_retrieval: bool,
    ) -> dict[str, object]:
        del user_id, k, seen_history_split, strict_retrieval
        return {
            "debug": {
                "mode": mode,
                "retrieved_from_es_movie_ids": [101, 102],
                "retrieved_from_es_scores": [3.0, 2.0],
            }
        }


class FakeEsForAudit:
    def search(self, *, index: str, query: dict[str, object], size: int):  # noqa: ARG002
        if index == "movies":
            hits = [
                {
                    "_id": "101",
                    "_score": 3.0,
                    "_source": {
                        "movie_id": "101",
                        "title": "Baseline One",
                        "genres": ["Drama"],
                        "synopsis": "baseline",
                    },
                },
                {
                    "_id": "102",
                    "_score": 2.0,
                    "_source": {
                        "movie_id": "102",
                        "title": "Baseline Two",
                        "genres": ["Comedy"],
                        "synopsis": "baseline",
                    },
                },
            ]
        else:
            hits = [
                {
                    "_id": "101",
                    "_score": 3.0,
                    "_source": {
                        "movie_id": "101",
                        "title": "Attacked One",
                        "genres": ["Drama"],
                        "synopsis": "attacked",
                        "poison_marker": True,
                        "poison_payload": "payload",
                    },
                }
            ]
        return ObjectResponse({"hits": {"hits": hits}})


class FakeEsForRunner:
    def search(self, *, index: str, query: dict[str, object], size: int):  # noqa: ARG002
        return ObjectResponse(
            {
                "hits": {
                    "hits": [
                        {
                            "_source": {
                                "movie_id": "42",
                                "poison_marker": True,
                                "poison_payload": "inject",
                                "synopsis": "keywords",
                            }
                        }
                    ]
                }
            }
        )


def test_retrieval_diff_supports_object_responses() -> None:
    summary = eval_audit._retrieval_diff_summary(
        users_service=FakeUsersService(),
        recs_service=FakeRecsService(),
        es_client=FakeEsForAudit(),
        llm_config=SimpleNamespace(ranking_mode="deterministic"),
        user_id=1,
    )

    assert summary["baseline_candidate_ids"] == [101, 102]
    assert summary["attacked_candidate_ids"] == [101]
    assert summary["candidate_ids_equal"] is False


def test_target_poison_validation_supports_object_responses() -> None:
    message = eval_runner._validate_target_poison_state(
        es_client=FakeEsForRunner(),
        attack_config=AttackConfig(
            attack_type="prompt_injection",
            poison_fraction=0.5,
            target_movie_id=42,
            payload_text="payload",
            keyword_list=["action"],
        ),
        target_movie_id=42,
    )

    assert message is not None
    assert "Validated target poison state" in message
    assert "poison_marker=true" in message
