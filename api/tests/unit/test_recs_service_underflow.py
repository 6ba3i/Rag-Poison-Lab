from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from api.app.services.recs_service import RecsService
from api.app.settings import Settings


class _SingleHitElasticsearch:
    def search(self, *, index: str, query: dict[str, Any], size: int) -> dict[str, Any]:
        del query, size
        source = {
            "movie_id": "2",
            "title": "Movie Two",
            "genres": ["Drama"],
            "synopsis": "single retrieved hit",
            "poison_marker": False,
            "poison_payload": "",
        }
        return {"hits": {"hits": [{"_id": "2", "_score": 2.0, "_source": source}]}}


def _build_settings(tmp_path: Path) -> Settings:
    data_dir = tmp_path / "data"
    processed_dir = data_dir / "processed"
    config_dir = data_dir / "config"
    processed_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        [
            {"movie_id": 1, "title": "Seen One", "genres": ["Action"]},
            {"movie_id": 2, "title": "Movie Two", "genres": ["Drama"]},
            {"movie_id": 3, "title": "Movie Three", "genres": ["Comedy"]},
            {"movie_id": 4, "title": "Movie Four", "genres": ["Action"]},
            {"movie_id": 5, "title": "Movie Five", "genres": ["Action"]},
        ]
    ).to_parquet(processed_dir / "movies.parquet", index=False)

    pd.DataFrame(
        [
            {"user_id": 1, "movie_id": 1, "rating": 5.0, "timestamp": 100},
            {"user_id": 2, "movie_id": 5, "rating": 5.0, "timestamp": 10},
            {"user_id": 3, "movie_id": 5, "rating": 4.0, "timestamp": 20},
            {"user_id": 4, "movie_id": 5, "rating": 4.0, "timestamp": 30},
            {"user_id": 2, "movie_id": 4, "rating": 4.0, "timestamp": 11},
            {"user_id": 3, "movie_id": 4, "rating": 3.0, "timestamp": 21},
            {"user_id": 4, "movie_id": 3, "rating": 5.0, "timestamp": 31},
        ]
    ).to_parquet(processed_dir / "ratings.parquet", index=False)

    pd.DataFrame(
        [
            {
                "user_id": 1,
                "rating_count": 1,
                "mean_rating": 5.0,
                "top_genres": '[{"count":1,"genre":"Action"}]',
                "top_rated_movie_ids": "[1]",
                "recent_movie_ids": "[1]",
            }
        ]
    ).to_parquet(processed_dir / "user_profiles.parquet", index=False)

    pd.DataFrame(
        [
            {"user_id": 1, "movie_id": 1, "rating": 5.0, "timestamp": 100, "split": "train"},
        ]
    ).to_parquet(processed_dir / "splits.parquet", index=False)

    settings = Settings(_env_file=None, data_root=data_dir, config_root=config_dir, processed_root=processed_dir)
    settings.resolved_llm_config_path.write_text(
        json.dumps(
            {
                "victim": {"provider": "local", "model": "qwen2.5:1.5b"},
                "attacker": {"provider": "local", "model": "qwen2.5:1.5b"},
                "ranking_mode": "deterministic",
                "retrieval_mode": "lexical",
            }
        ),
        encoding="utf-8",
    )
    return settings


def test_underflow_fallback_uses_popularity_prior(tmp_path: Path) -> None:
    service = RecsService(settings=_build_settings(tmp_path), es_client=_SingleHitElasticsearch(), llm_registry=None)

    result = service.recommend_with_debug(
        user_id=1,
        mode="baseline",
        k=3,
        seen_history_split="train",
        strict_retrieval=False,
    )

    debug = result["debug"]
    assert debug["retrieval_underflow"] is True
    assert debug["strict_underflow"] is False
    assert debug["fallback_used"] is True
    assert debug["fallback_added"] == 2
    assert debug["fallback_policy"] == "ratings_popularity_prior"
    assert debug["fallback_movie_ids"] == [5, 4]
    assert len(result["items"]) == 3


def test_underflow_strict_mode_skips_filler(tmp_path: Path) -> None:
    service = RecsService(settings=_build_settings(tmp_path), es_client=_SingleHitElasticsearch(), llm_registry=None)

    result = service.recommend_with_debug(
        user_id=1,
        mode="baseline",
        k=3,
        seen_history_split="train",
        strict_retrieval=True,
    )

    debug = result["debug"]
    assert debug["retrieval_underflow"] is True
    assert debug["strict_underflow"] is True
    assert debug["fallback_used"] is False
    assert debug["fallback_added"] == 0
    assert debug["fallback_policy"] == "none"
    assert debug["fallback_movie_ids"] == []
    assert debug["fallback_skipped_reason"] == "strict_retrieval_no_filler"
    assert debug["ranking_input_movie_ids"] == [2]
    assert len(result["items"]) == 1
