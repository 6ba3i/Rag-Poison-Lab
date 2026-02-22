from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class MovieLensFiles:
    ratings: Path
    movies: Path
    genres: Path
    users: Path | None


@dataclass(frozen=True)
class LoadedMovieLensData:
    files: MovieLensFiles
    ratings: pd.DataFrame
    movies: pd.DataFrame
    users: pd.DataFrame | None


def _read_sample_lines(path: Path, max_lines: int = 5) -> list[str]:
    lines: list[str] = []
    with path.open("r", encoding="latin-1", errors="ignore") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            lines.append(stripped)
            if len(lines) >= max_lines:
                break
    return lines


def _is_int(value: str) -> bool:
    try:
        int(value)
    except ValueError:
        return False
    return True


def _looks_like_ratings(path: Path) -> bool:
    lines = _read_sample_lines(path)
    if not lines:
        return False
    for line in lines:
        fields = line.split("\t")
        if len(fields) != 4:
            return False
        if not all(_is_int(part) for part in fields):
            return False
    return True


def _looks_like_movies(path: Path) -> bool:
    lines = _read_sample_lines(path)
    if not lines:
        return False
    fields = lines[0].split("|")
    if len(fields) < 24:
        return False
    if not _is_int(fields[0]) or not fields[1]:
        return False
    genre_flags = fields[5:]
    return len(genre_flags) >= 19 and all(flag in {"0", "1"} for flag in genre_flags[:19])


def _looks_like_genres(path: Path) -> bool:
    lines = _read_sample_lines(path)
    if not lines:
        return False
    fields = lines[0].split("|")
    return len(fields) == 2 and bool(fields[0]) and _is_int(fields[1])


def _looks_like_users(path: Path) -> bool:
    lines = _read_sample_lines(path)
    if not lines:
        return False
    fields = lines[0].split("|")
    if len(fields) != 5:
        return False
    return _is_int(fields[0]) and _is_int(fields[1]) and fields[2] in {"M", "F"}


def _choose_file(candidates: list[Path], preferred_names: tuple[str, ...], role: str) -> Path:
    if not candidates:
        raise FileNotFoundError(f"Could not detect MovieLens {role} file")

    preferences = {name: index for index, name in enumerate(preferred_names)}

    def rank(path: Path) -> tuple[int, int, str]:
        preference = preferences.get(path.name, len(preferred_names))
        size_rank = -path.stat().st_size
        return (preference, size_rank, path.name)

    return sorted(candidates, key=rank)[0]


def detect_movielens_files(dataset_dir: str | Path) -> MovieLensFiles:
    base_dir = Path(dataset_dir).resolve()
    if not base_dir.exists() or not base_dir.is_dir():
        raise FileNotFoundError(f"Dataset directory does not exist: {base_dir}")

    files = [path for path in base_dir.iterdir() if path.is_file() and not path.name.startswith(".")]

    ratings_candidates = [path for path in files if _looks_like_ratings(path)]
    movies_candidates = [path for path in files if _looks_like_movies(path)]
    genres_candidates = [path for path in files if _looks_like_genres(path)]
    users_candidates = [path for path in files if _looks_like_users(path)]

    ratings = _choose_file(
        ratings_candidates,
        preferred_names=("u.data", "ratings.tsv", "ratings.txt"),
        role="ratings",
    )
    movies = _choose_file(
        movies_candidates,
        preferred_names=("u.item", "movies.tsv", "movies.txt"),
        role="movies",
    )
    genres = _choose_file(
        genres_candidates,
        preferred_names=("u.genre", "genres.tsv", "genres.txt"),
        role="genres",
    )
    users = (
        _choose_file(
            users_candidates,
            preferred_names=("u.user", "users.tsv", "users.txt"),
            role="users",
        )
        if users_candidates
        else None
    )

    return MovieLensFiles(ratings=ratings, movies=movies, genres=genres, users=users)


def _validate_required_columns(df: pd.DataFrame, columns: tuple[str, ...], dataset_name: str) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in {dataset_name}: {missing}")


def _validate_no_nulls(df: pd.DataFrame, columns: tuple[str, ...], dataset_name: str) -> None:
    null_columns = [column for column in columns if df[column].isnull().any()]
    if null_columns:
        raise ValueError(f"Null values detected in required {dataset_name} columns: {null_columns}")


def load_ratings(ratings_file: Path) -> pd.DataFrame:
    ratings = pd.read_csv(
        ratings_file,
        sep="\t",
        names=["user_id", "movie_id", "rating", "timestamp"],
        header=None,
        engine="python",
    )

    _validate_required_columns(ratings, ("user_id", "movie_id", "rating", "timestamp"), "ratings")

    for column in ("user_id", "movie_id", "rating", "timestamp"):
        ratings[column] = pd.to_numeric(ratings[column], errors="raise").astype("int64")

    _validate_no_nulls(ratings, ("user_id", "movie_id", "rating", "timestamp"), "ratings")

    ratings = ratings.sort_values(["user_id", "timestamp", "movie_id"], kind="mergesort").reset_index(drop=True)
    return ratings


def load_genres(genres_file: Path) -> list[str]:
    genres = pd.read_csv(
        genres_file,
        sep="|",
        names=["genre", "genre_id"],
        header=None,
        usecols=[0, 1],
        engine="python",
        encoding="latin-1",
    )

    genres = genres.dropna(subset=["genre", "genre_id"])  # Drops the terminal "|" row in MovieLens files.
    genres["genre"] = genres["genre"].astype(str).str.strip()
    genres = genres[genres["genre"] != ""]
    genres["genre_id"] = pd.to_numeric(genres["genre_id"], errors="raise").astype("int64")

    ordered = genres.sort_values("genre_id", kind="mergesort")
    if ordered.empty:
        raise ValueError("No genres were detected in genres file")

    return ordered["genre"].tolist()


def load_movies(movies_file: Path, genre_names: list[str]) -> pd.DataFrame:
    if not genre_names:
        raise ValueError("Genre list cannot be empty")

    base_columns = ["movie_id", "title", "release_date", "video_release_date", "imdb_url"]
    genre_columns = [f"genre_flag_{idx}" for idx in range(len(genre_names))]
    columns = base_columns + genre_columns

    movies = pd.read_csv(
        movies_file,
        sep="|",
        names=columns,
        usecols=list(range(len(columns))),
        header=None,
        engine="python",
        encoding="latin-1",
    )

    _validate_required_columns(movies, ("movie_id", "title"), "movies")

    movies["movie_id"] = pd.to_numeric(movies["movie_id"], errors="raise").astype("int64")
    movies["title"] = movies["title"].astype(str).str.strip()

    for column in genre_columns:
        movies[column] = pd.to_numeric(movies[column], errors="coerce").fillna(0).astype("int64")

    _validate_no_nulls(movies, ("movie_id", "title"), "movies")

    genre_matrix = movies[genre_columns].to_numpy(dtype="int64")
    genres_by_movie: list[list[str]] = []
    for row in genre_matrix:
        genres_by_movie.append([genre_names[idx] for idx, flag in enumerate(row) if flag == 1])

    result = movies[["movie_id", "title"]].copy()
    result["genres"] = genres_by_movie
    result = result.sort_values("movie_id", kind="mergesort").reset_index(drop=True)

    if result.empty:
        raise ValueError("No movies were loaded")

    return result


def load_users(users_file: Path) -> pd.DataFrame:
    users = pd.read_csv(
        users_file,
        sep="|",
        names=["user_id", "age", "gender", "occupation", "zip_code"],
        header=None,
        engine="python",
        encoding="latin-1",
    )

    users["user_id"] = pd.to_numeric(users["user_id"], errors="raise").astype("int64")
    users["age"] = pd.to_numeric(users["age"], errors="raise").astype("int64")

    _validate_no_nulls(users, ("user_id", "age", "gender"), "users")

    return users.sort_values("user_id", kind="mergesort").reset_index(drop=True)


def load_movielens_dataset(dataset_dir: str | Path) -> LoadedMovieLensData:
    files = detect_movielens_files(dataset_dir)
    genres = load_genres(files.genres)
    ratings = load_ratings(files.ratings)
    movies = load_movies(files.movies, genres)
    users = load_users(files.users) if files.users is not None else None

    if len(ratings) == 0:
        raise ValueError("Ratings dataset is empty")

    return LoadedMovieLensData(files=files, ratings=ratings, movies=movies, users=users)
