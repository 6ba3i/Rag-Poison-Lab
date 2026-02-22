from __future__ import annotations

from pathlib import Path
from typing import Final

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
WORKSPACE_ROOT: Final[Path] = Path("/workspace")

MOVIES_PARQUET: Final[str] = "movies.parquet"
RATINGS_PARQUET: Final[str] = "ratings.parquet"
USER_PROFILES_PARQUET: Final[str] = "user_profiles.parquet"
SPLITS_PARQUET: Final[str] = "splits.parquet"
ES_BULK_MOVIES_JSONL: Final[str] = "es_bulk_movies.jsonl"
ES_BULK_POISONED_MOVIES_JSONL: Final[str] = "es_bulk_poisoned_movies.jsonl"


def resolve_default_dataset_dir() -> Path:
    workspace_dataset = WORKSPACE_ROOT / "ml-100"
    if workspace_dataset.exists():
        return workspace_dataset
    return REPO_ROOT / "ml-100"


def resolve_default_processed_dir() -> Path:
    workspace_data = WORKSPACE_ROOT / "data"
    if workspace_data.exists():
        return workspace_data / "processed"
    return REPO_ROOT / "data" / "processed"


def resolve_dataset_dir(dataset_dir: str | Path | None = None) -> Path:
    path = Path(dataset_dir) if dataset_dir is not None else resolve_default_dataset_dir()
    return path.resolve()


def resolve_output_dir(output_dir: str | Path | None = None, *, create: bool = True) -> Path:
    path = Path(output_dir) if output_dir is not None else resolve_default_processed_dir()
    resolved = path.resolve()
    if create:
        resolved.mkdir(parents=True, exist_ok=True)
    return resolved
