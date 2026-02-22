from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pandas as pd

from api.app.data.movielens_loader import detect_movielens_files, load_movielens_dataset
from api.app.data.preprocess import prepare_pipeline
from api.app.data.splits import build_train_test_splits


GENRES = [
    "unknown",
    "Action",
    "Adventure",
    "Animation",
    "Children's",
    "Comedy",
    "Crime",
    "Documentary",
    "Drama",
    "Fantasy",
    "Film-Noir",
    "Horror",
    "Musical",
    "Mystery",
    "Romance",
    "Sci-Fi",
    "Thriller",
    "War",
    "Western",
]


def _flags(*genre_names: str) -> list[int]:
    selected = set(genre_names)
    return [1 if genre in selected else 0 for genre in GENRES]


def _movie_line(movie_id: int, title: str, flags: list[int]) -> str:
    fields = [
        str(movie_id),
        title,
        "01-Jan-1995",
        "",
        f"http://example.com/{movie_id}",
        *[str(flag) for flag in flags],
    ]
    return "|".join(fields)


def _write_mock_dataset(dataset_dir: Path, *, nonstandard_names: bool = False) -> dict[str, Path]:
    dataset_dir.mkdir(parents=True, exist_ok=True)

    names = {
        "ratings": "ratings_source.tsv" if nonstandard_names else "u.data",
        "movies": "movies_source.psv" if nonstandard_names else "u.item",
        "genres": "genre_lookup.tbl" if nonstandard_names else "u.genre",
        "users": "people_source.txt" if nonstandard_names else "u.user",
    }

    ratings_lines = [
        "1\t1\t5\t100",
        "1\t2\t3\t200",
        "1\t3\t4\t300",
        "2\t1\t2\t110",
        "2\t3\t5\t120",
        "2\t4\t4\t130",
        "3\t2\t4\t400",
        "3\t4\t1\t500",
    ]

    movies_lines = [
        _movie_line(1, "Movie One", _flags("Action", "Comedy")),
        _movie_line(2, "Movie Two", _flags("Drama")),
        _movie_line(3, "Movie Three", _flags("Sci-Fi", "Action")),
        _movie_line(4, "Movie Four", _flags("Romance", "Drama")),
    ]

    genres_lines = [f"{genre}|{idx}" for idx, genre in enumerate(GENRES)] + ["|"]
    users_lines = [
        "1|24|M|student|00001",
        "2|30|F|engineer|00002",
        "3|35|M|writer|00003",
    ]

    paths = {key: dataset_dir / filename for key, filename in names.items()}
    paths["ratings"].write_text("\n".join(ratings_lines) + "\n", encoding="utf-8")
    paths["movies"].write_text("\n".join(movies_lines) + "\n", encoding="latin-1")
    paths["genres"].write_text("\n".join(genres_lines) + "\n", encoding="utf-8")
    paths["users"].write_text("\n".join(users_lines) + "\n", encoding="utf-8")

    return paths


def _file_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def test_file_detection_with_nonstandard_names(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "dataset"
    paths = _write_mock_dataset(dataset_dir, nonstandard_names=True)

    detected = detect_movielens_files(dataset_dir)

    assert detected.ratings == paths["ratings"]
    assert detected.movies == paths["movies"]
    assert detected.genres == paths["genres"]
    assert detected.users == paths["users"]


def test_row_counts_positive_after_prepare(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "dataset"
    output_dir = tmp_path / "processed"
    _write_mock_dataset(dataset_dir)

    summary = prepare_pipeline(dataset_dir=dataset_dir, output_dir=output_dir, test_holdout=2)

    assert summary["movies_rows"] > 0
    assert summary["ratings_rows"] > 0
    assert summary["splits_rows"] > 0
    assert summary["profiles_rows"] > 0
    assert summary["es_bulk_docs"] > 0
    assert summary["es_bulk_poisoned_docs"] > 0


def test_split_correctness_per_user(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "dataset"
    _write_mock_dataset(dataset_dir)

    loaded = load_movielens_dataset(dataset_dir)
    splits = build_train_test_splits(loaded.ratings, test_holdout=2)

    total_counts = splits.groupby("user_id").size().to_dict()
    test_counts = splits[splits["split"] == "test"].groupby("user_id").size().to_dict()

    for user_id, total in total_counts.items():
        assert test_counts[user_id] == min(2, total)

    for user_id, group in splits.groupby("user_id"):
        train = group[group["split"] == "train"]
        test = group[group["split"] == "test"]
        if not train.empty and not test.empty:
            assert int(train["timestamp"].max()) <= int(test["timestamp"].min())


def test_deterministic_outputs_same_input(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "dataset"
    out_a = tmp_path / "out_a"
    out_b = tmp_path / "out_b"
    _write_mock_dataset(dataset_dir)

    prepare_pipeline(dataset_dir=dataset_dir, output_dir=out_a, test_holdout=2)
    prepare_pipeline(dataset_dir=dataset_dir, output_dir=out_b, test_holdout=2)

    required = [
        "movies.parquet",
        "ratings.parquet",
        "user_profiles.parquet",
        "splits.parquet",
        "es_bulk_movies.jsonl",
        "es_bulk_poisoned_movies.jsonl",
    ]

    hashes_a = {name: _file_hash(out_a / name) for name in required}
    hashes_b = {name: _file_hash(out_b / name) for name in required}

    assert hashes_a == hashes_b

    splits_a = pd.read_parquet(out_a / "splits.parquet")
    splits_b = pd.read_parquet(out_b / "splits.parquet")
    assert splits_a.equals(splits_b)


def test_poisoned_bulk_structure(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "dataset"
    output_dir = tmp_path / "processed"
    _write_mock_dataset(dataset_dir)

    prepare_pipeline(dataset_dir=dataset_dir, output_dir=output_dir, test_holdout=2)

    poisoned_path = output_dir / "es_bulk_poisoned_movies.jsonl"
    lines = poisoned_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) > 0
    assert len(lines) % 2 == 0

    for line_idx in range(0, len(lines), 2):
        action = json.loads(lines[line_idx])
        doc = json.loads(lines[line_idx + 1])

        assert action["index"]["_index"] == "movies_poisoned"
        assert action["index"]["_id"] == doc["movie_id"]
        assert isinstance(doc["genres"], list)
        assert doc["poison_marker"] is False
        assert doc["poison_payload"] == ""
