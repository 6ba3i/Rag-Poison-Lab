from __future__ import annotations

import numpy as np
import pandas as pd


REQUIRED_RATINGS_COLUMNS = ("user_id", "movie_id", "rating", "timestamp")


def build_train_test_splits(ratings_df: pd.DataFrame, test_holdout: int = 10) -> pd.DataFrame:
    if test_holdout <= 0:
        raise ValueError("test_holdout must be greater than 0")

    missing = [column for column in REQUIRED_RATINGS_COLUMNS if column not in ratings_df.columns]
    if missing:
        raise ValueError(f"ratings_df missing required columns: {missing}")

    if ratings_df[list(REQUIRED_RATINGS_COLUMNS)].isnull().any().any():
        raise ValueError("ratings_df contains nulls in required columns")

    df = ratings_df.loc[:, list(REQUIRED_RATINGS_COLUMNS)].copy()

    for column in REQUIRED_RATINGS_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="raise")

    df["user_id"] = df["user_id"].astype("int64")
    df["movie_id"] = df["movie_id"].astype("int64")
    df["rating"] = df["rating"].astype("float64")
    df["timestamp"] = df["timestamp"].astype("int64")

    df = df.sort_values(["user_id", "timestamp", "movie_id"], kind="mergesort").reset_index(drop=True)

    user_sizes = df.groupby("user_id")["movie_id"].transform("size")
    position_in_user = df.groupby("user_id").cumcount()
    test_start = (user_sizes - test_holdout).clip(lower=0)

    df["split"] = np.where(position_in_user >= test_start, "test", "train")

    return df[["user_id", "movie_id", "rating", "timestamp", "split"]]
