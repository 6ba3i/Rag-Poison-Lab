from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

import pandas as pd

from api.app.data.movielens_loader import load_movielens_dataset
from api.app.data.paths import (
    ES_BULK_MOVIES_JSONL,
    ES_BULK_POISONED_MOVIES_JSONL,
    MOVIES_PARQUET,
    RATINGS_PARQUET,
    SPLITS_PARQUET,
    USER_PROFILES_PARQUET,
    resolve_dataset_dir,
    resolve_output_dir,
)
from api.app.data.profiles import build_user_profiles
from api.app.data.splits import build_train_test_splits


def _write_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, engine="pyarrow", index=False)


def _normalize_genre_payload(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("["):
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        if text == "":
            return []
        return [part for part in text.split("|") if part]
    return []


def _prepare_movies_for_es(movies_df: pd.DataFrame) -> pd.DataFrame:
    required = {"movie_id", "title", "genres"}
    missing = required - set(movies_df.columns)
    if missing:
        raise ValueError(f"movies_df missing required columns: {sorted(missing)}")

    ordered = movies_df[["movie_id", "title", "genres"]].copy()
    ordered["movie_id"] = pd.to_numeric(ordered["movie_id"], errors="raise").astype("int64")
    ordered["title"] = ordered["title"].astype(str)
    return ordered.sort_values("movie_id", kind="mergesort").reset_index(drop=True)


def _write_bulk_movies(
    *,
    movies_df: pd.DataFrame,
    output_file: Path,
    index_name: str,
    include_poison_fields: bool,
) -> int:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    ordered = _prepare_movies_for_es(movies_df)

    count = 0
    with output_file.open("w", encoding="utf-8", newline="\n") as handle:
        for row in ordered.itertuples(index=False):
            movie_id = int(row.movie_id)
            action = {"index": {"_index": index_name, "_id": str(movie_id)}}
            doc = {
                "movie_id": str(movie_id),
                "title": str(row.title),
                "genres": _normalize_genre_payload(row.genres),
                "synopsis": "",
            }
            if include_poison_fields:
                doc["poison_marker"] = False
                doc["poison_payload"] = ""
            handle.write(json.dumps(action, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
            handle.write("\n")
            handle.write(json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
            handle.write("\n")
            count += 1

    return count


def export_es_bulk_movies(movies_df: pd.DataFrame, output_file: Path) -> int:
    return _write_bulk_movies(
        movies_df=movies_df,
        output_file=output_file,
        index_name="movies",
        include_poison_fields=False,
    )


def export_es_bulk_poisoned_movies(movies_df: pd.DataFrame, output_file: Path) -> int:
    return _write_bulk_movies(
        movies_df=movies_df,
        output_file=output_file,
        index_name="movies_poisoned",
        include_poison_fields=True,
    )


def _hash_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def prepare_pipeline(
    *,
    dataset_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
    test_holdout: int = 10,
    top_genres_k: int = 5,
    top_rated_k: int = 10,
    recent_k: int = 10,
) -> dict[str, Any]:
    dataset_path = resolve_dataset_dir(dataset_dir)
    output_path = resolve_output_dir(output_dir)

    loaded = load_movielens_dataset(dataset_path)

    ratings = loaded.ratings.sort_values(["user_id", "timestamp", "movie_id"], kind="mergesort").reset_index(drop=True)
    movies = loaded.movies.sort_values(["movie_id"], kind="mergesort").reset_index(drop=True)
    splits = build_train_test_splits(ratings, test_holdout=test_holdout)
    profiles = build_user_profiles(
        ratings,
        movies,
        top_genres_k=top_genres_k,
        top_rated_k=top_rated_k,
        recent_k=recent_k,
    )

    movies_path = output_path / MOVIES_PARQUET
    ratings_path = output_path / RATINGS_PARQUET
    splits_path = output_path / SPLITS_PARQUET
    profiles_path = output_path / USER_PROFILES_PARQUET
    bulk_path = output_path / ES_BULK_MOVIES_JSONL
    bulk_poisoned_path = output_path / ES_BULK_POISONED_MOVIES_JSONL

    _write_parquet(movies, movies_path)
    _write_parquet(ratings, ratings_path)
    _write_parquet(splits, splits_path)
    _write_parquet(profiles, profiles_path)
    bulk_count = export_es_bulk_movies(movies, bulk_path)
    bulk_poisoned_count = export_es_bulk_poisoned_movies(movies, bulk_poisoned_path)

    return {
        "dataset_dir": str(dataset_path),
        "output_dir": str(output_path),
        "movies_rows": int(len(movies)),
        "ratings_rows": int(len(ratings)),
        "splits_rows": int(len(splits)),
        "profiles_rows": int(len(profiles)),
        "es_bulk_docs": int(bulk_count),
        "es_bulk_poisoned_docs": int(bulk_poisoned_count),
        "movies_path": str(movies_path),
        "ratings_path": str(ratings_path),
        "splits_path": str(splits_path),
        "profiles_path": str(profiles_path),
        "es_bulk_path": str(bulk_path),
        "es_bulk_poisoned_path": str(bulk_poisoned_path),
        "hashes": {
            MOVIES_PARQUET: _hash_file(movies_path),
            RATINGS_PARQUET: _hash_file(ratings_path),
            SPLITS_PARQUET: _hash_file(splits_path),
            USER_PROFILES_PARQUET: _hash_file(profiles_path),
            ES_BULK_MOVIES_JSONL: _hash_file(bulk_path),
            ES_BULK_POISONED_MOVIES_JSONL: _hash_file(bulk_poisoned_path),
        },
    }


def profiles_pipeline(
    *,
    dataset_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
    top_genres_k: int = 5,
    top_rated_k: int = 10,
    recent_k: int = 10,
) -> dict[str, Any]:
    dataset_path = resolve_dataset_dir(dataset_dir)
    output_path = resolve_output_dir(output_dir)

    loaded = load_movielens_dataset(dataset_path)
    profiles = build_user_profiles(
        loaded.ratings,
        loaded.movies,
        top_genres_k=top_genres_k,
        top_rated_k=top_rated_k,
        recent_k=recent_k,
    )

    profiles_path = output_path / USER_PROFILES_PARQUET
    _write_parquet(profiles, profiles_path)

    return {
        "dataset_dir": str(dataset_path),
        "output_dir": str(output_path),
        "profiles_rows": int(len(profiles)),
        "profiles_path": str(profiles_path),
        "hash": _hash_file(profiles_path),
    }


def splits_pipeline(
    *,
    dataset_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
    test_holdout: int = 10,
) -> dict[str, Any]:
    dataset_path = resolve_dataset_dir(dataset_dir)
    output_path = resolve_output_dir(output_dir)

    loaded = load_movielens_dataset(dataset_path)
    splits = build_train_test_splits(loaded.ratings, test_holdout=test_holdout)

    splits_path = output_path / SPLITS_PARQUET
    _write_parquet(splits, splits_path)

    return {
        "dataset_dir": str(dataset_path),
        "output_dir": str(output_path),
        "splits_rows": int(len(splits)),
        "splits_path": str(splits_path),
        "hash": _hash_file(splits_path),
    }


def export_es_pipeline(
    *,
    dataset_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    dataset_path = resolve_dataset_dir(dataset_dir)
    output_path = resolve_output_dir(output_dir)

    loaded = load_movielens_dataset(dataset_path)
    bulk_path = output_path / ES_BULK_MOVIES_JSONL
    bulk_poisoned_path = output_path / ES_BULK_POISONED_MOVIES_JSONL
    docs = export_es_bulk_movies(loaded.movies, bulk_path)
    poisoned_docs = export_es_bulk_poisoned_movies(loaded.movies, bulk_poisoned_path)

    return {
        "dataset_dir": str(dataset_path),
        "output_dir": str(output_path),
        "es_bulk_docs": int(docs),
        "es_bulk_poisoned_docs": int(poisoned_docs),
        "es_bulk_path": str(bulk_path),
        "es_bulk_poisoned_path": str(bulk_poisoned_path),
        "hash": _hash_file(bulk_path),
        "poisoned_hash": _hash_file(bulk_poisoned_path),
    }
