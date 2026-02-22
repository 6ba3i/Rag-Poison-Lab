from __future__ import annotations

import json
from collections import defaultdict

import pandas as pd


def _json_dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _normalize_genres(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    if isinstance(value, str):
        text = value.strip()
        if text == "":
            return []
        if text.startswith("["):
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item) for item in parsed if str(item)]
        return [part for part in text.split("|") if part]
    return []


def build_user_profiles(
    ratings_df: pd.DataFrame,
    movies_df: pd.DataFrame,
    *,
    top_genres_k: int = 5,
    top_rated_k: int = 10,
    recent_k: int = 10,
) -> pd.DataFrame:
    if min(top_genres_k, top_rated_k, recent_k) <= 0:
        raise ValueError("top_genres_k, top_rated_k, and recent_k must all be > 0")

    required_rating_cols = {"user_id", "movie_id", "rating", "timestamp"}
    required_movie_cols = {"movie_id", "genres"}

    if not required_rating_cols.issubset(ratings_df.columns):
        missing = sorted(required_rating_cols - set(ratings_df.columns))
        raise ValueError(f"ratings_df missing required columns: {missing}")

    if not required_movie_cols.issubset(movies_df.columns):
        missing = sorted(required_movie_cols - set(movies_df.columns))
        raise ValueError(f"movies_df missing required columns: {missing}")

    if ratings_df[list(required_rating_cols)].isnull().any().any():
        raise ValueError("ratings_df contains nulls in required columns")

    ratings = ratings_df[["user_id", "movie_id", "rating", "timestamp"]].copy()
    ratings["user_id"] = pd.to_numeric(ratings["user_id"], errors="raise").astype("int64")
    ratings["movie_id"] = pd.to_numeric(ratings["movie_id"], errors="raise").astype("int64")
    ratings["rating"] = pd.to_numeric(ratings["rating"], errors="raise").astype("float64")
    ratings["timestamp"] = pd.to_numeric(ratings["timestamp"], errors="raise").astype("int64")

    movies = movies_df[["movie_id", "genres"]].copy()
    movies["movie_id"] = pd.to_numeric(movies["movie_id"], errors="raise").astype("int64")
    movies["genres"] = movies["genres"].map(_normalize_genres)

    summary = (
        ratings.groupby("user_id", as_index=False)
        .agg(rating_count=("movie_id", "size"), mean_rating=("rating", "mean"))
        .sort_values("user_id", kind="mergesort")
        .reset_index(drop=True)
    )
    summary["mean_rating"] = summary["mean_rating"].round(6)

    recent_source = ratings.sort_values(
        ["user_id", "timestamp", "movie_id"], ascending=[True, False, True], kind="mergesort"
    )
    recent_rows = recent_source.groupby("user_id", sort=False).head(recent_k)
    recent_map = recent_rows.groupby("user_id", sort=True)["movie_id"].apply(list).to_dict()

    top_rated_source = ratings.sort_values(
        ["user_id", "rating", "timestamp", "movie_id"],
        ascending=[True, False, False, True],
        kind="mergesort",
    )
    top_rated_rows = top_rated_source.groupby("user_id", sort=False).head(top_rated_k)
    top_rated_map = top_rated_rows.groupby("user_id", sort=True)["movie_id"].apply(list).to_dict()

    ratings_with_genres = ratings[["user_id", "movie_id"]].merge(movies, on="movie_id", how="left")
    ratings_with_genres["genres"] = ratings_with_genres["genres"].map(lambda value: value if isinstance(value, list) else [])

    exploded = ratings_with_genres.explode("genres")
    exploded = exploded.dropna(subset=["genres"])

    genre_counts = (
        exploded.groupby(["user_id", "genres"], as_index=False)
        .size()
        .rename(columns={"size": "count"})
        .sort_values(["user_id", "count", "genres"], ascending=[True, False, True], kind="mergesort")
    )
    top_genre_rows = genre_counts.groupby("user_id", sort=False).head(top_genres_k)

    top_genres_map: dict[int, list[dict[str, int | str]]] = defaultdict(list)
    for row in top_genre_rows.itertuples(index=False):
        top_genres_map[int(row.user_id)].append({"genre": str(row.genres), "count": int(row.count)})

    summary["top_genres"] = summary["user_id"].map(lambda user_id: _json_dumps(top_genres_map.get(int(user_id), [])))
    summary["top_rated_movie_ids"] = summary["user_id"].map(
        lambda user_id: _json_dumps([int(movie_id) for movie_id in top_rated_map.get(int(user_id), [])])
    )
    summary["recent_movie_ids"] = summary["user_id"].map(
        lambda user_id: _json_dumps([int(movie_id) for movie_id in recent_map.get(int(user_id), [])])
    )

    return summary[
        ["user_id", "rating_count", "mean_rating", "top_genres", "top_rated_movie_ids", "recent_movie_ids"]
    ]
