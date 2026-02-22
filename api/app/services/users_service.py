from __future__ import annotations

import json
from functools import cached_property
from pathlib import Path
from typing import Any

import pandas as pd

from api.app.data.paths import MOVIES_PARQUET, RATINGS_PARQUET, SPLITS_PARQUET, USER_PROFILES_PARQUET
from api.app.settings import Settings


class UsersService:
    def __init__(self, *, settings: Settings) -> None:
        self.settings = settings

    @cached_property
    def movies_df(self) -> pd.DataFrame:
        return _read_parquet(self.settings.resolved_processed_dir / MOVIES_PARQUET)

    @cached_property
    def ratings_df(self) -> pd.DataFrame:
        return _read_parquet(self.settings.resolved_processed_dir / RATINGS_PARQUET)

    @cached_property
    def profiles_df(self) -> pd.DataFrame:
        return _read_parquet(self.settings.resolved_processed_dir / USER_PROFILES_PARQUET)

    @cached_property
    def splits_df(self) -> pd.DataFrame:
        return _read_parquet(self.settings.resolved_processed_dir / SPLITS_PARQUET)

    def list_users(self, *, q: str = "", limit: int = 50) -> list[dict[str, Any]]:
        profiles = self.profiles_df.copy()
        profiles["user_id"] = pd.to_numeric(profiles["user_id"], errors="coerce").fillna(-1).astype("int64")
        profiles["rating_count"] = pd.to_numeric(profiles["rating_count"], errors="coerce").fillna(0).astype("int64")
        profiles["mean_rating"] = pd.to_numeric(profiles["mean_rating"], errors="coerce").fillna(0.0).astype("float64")

        filtered = profiles.sort_values("user_id", kind="mergesort")
        query = q.strip().lower()
        if query:
            filtered = filtered[filtered["user_id"].astype(str).str.contains(query, regex=False)]

        limited = filtered.head(limit)
        output: list[dict[str, Any]] = []
        for row in limited.itertuples(index=False):
            output.append(
                {
                    "user_id": int(row.user_id),
                    "rating_count": int(row.rating_count),
                    "mean_rating": float(row.mean_rating),
                }
            )
        return output

    def get_profile(self, user_id: int) -> dict[str, Any] | None:
        profiles = self.profiles_df
        row = profiles[profiles["user_id"] == user_id]
        if row.empty:
            return None

        record = row.iloc[0]
        top_genres_raw = _parse_json_list(record.get("top_genres", "[]"))
        top_genres: list[dict[str, Any]] = []
        for item in top_genres_raw:
            if isinstance(item, dict):
                genre = str(item.get("genre", "")).strip()
                count = int(item.get("count", 0))
                if genre:
                    top_genres.append({"genre": genre, "count": count})

        return {
            "user_id": int(record["user_id"]),
            "rating_count": int(record["rating_count"]),
            "mean_rating": float(record["mean_rating"]),
            "top_genres": top_genres,
            "top_rated_movie_ids": _parse_int_list(record.get("top_rated_movie_ids", "[]")),
            "recent_movie_ids": _parse_int_list(record.get("recent_movie_ids", "[]")),
        }

    def get_history(self, user_id: int, split: str) -> list[dict[str, Any]]:
        ratings = self.ratings_df.copy()
        ratings = ratings[ratings["user_id"] == user_id]
        if ratings.empty:
            return []

        ratings["user_id"] = pd.to_numeric(ratings["user_id"], errors="raise").astype("int64")
        ratings["movie_id"] = pd.to_numeric(ratings["movie_id"], errors="raise").astype("int64")
        ratings["rating"] = pd.to_numeric(ratings["rating"], errors="raise").astype("float64")
        ratings["timestamp"] = pd.to_numeric(ratings["timestamp"], errors="raise").astype("int64")

        splits = self.splits_df.copy()
        splits = splits[splits["user_id"] == user_id]
        if not splits.empty:
            splits["user_id"] = pd.to_numeric(splits["user_id"], errors="raise").astype("int64")
            splits["movie_id"] = pd.to_numeric(splits["movie_id"], errors="raise").astype("int64")
            splits["timestamp"] = pd.to_numeric(splits["timestamp"], errors="raise").astype("int64")
            splits["split"] = splits["split"].astype(str)

        splits_subset = (
            splits[["user_id", "movie_id", "timestamp", "split"]]
            if not splits.empty
            else pd.DataFrame(columns=["user_id", "movie_id", "timestamp", "split"])
        )

        merged = ratings.merge(splits_subset, on=["user_id", "movie_id", "timestamp"], how="left")

        if split == "train":
            merged = merged[merged["split"] == "train"]

        movies = self.movies_df.copy()
        movies["movie_id"] = pd.to_numeric(movies["movie_id"], errors="raise").astype("int64")
        merged = merged.merge(movies[["movie_id", "title", "genres"]], on="movie_id", how="left")
        merged = merged.sort_values(["timestamp", "movie_id"], ascending=[False, True], kind="mergesort")

        output: list[dict[str, Any]] = []
        for row in merged.itertuples(index=False):
            output.append(
                {
                    "movie_id": int(row.movie_id),
                    "title": str(getattr(row, "title", "")),
                    "rating": float(row.rating),
                    "timestamp": int(row.timestamp),
                    "genres": _normalize_genres(getattr(row, "genres", [])),
                    "split": str(getattr(row, "split", "")) if getattr(row, "split", None) else None,
                }
            )

        return output


def _read_parquet(path: Path | str) -> pd.DataFrame:
    parquet_path = Path(path)
    if not parquet_path.exists() or not parquet_path.is_file():
        raise FileNotFoundError(f"Required parquet file not found: {parquet_path}")
    return pd.read_parquet(parquet_path)


def _parse_json_list(raw: object) -> list[Any]:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        text = raw.strip()
        if text == "":
            return []
        try:
            parsed = json.loads(text)
        except Exception:  # noqa: BLE001
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def _parse_int_list(raw: object) -> list[int]:
    values = _parse_json_list(raw)
    output: list[int] = []
    for value in values:
        try:
            output.append(int(value))
        except Exception:  # noqa: BLE001
            continue
    return output


def _normalize_genres(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]

    to_list = getattr(value, "tolist", None)
    if callable(to_list):
        raw = to_list()
        if isinstance(raw, list):
            return [str(item) for item in raw if str(item)]

    if isinstance(value, str):
        text = value.strip()
        if text.startswith("["):
            parsed = _parse_json_list(text)
            return [str(item) for item in parsed if str(item)]
        if text == "":
            return []
        return [part for part in text.split("|") if part]

    return []
