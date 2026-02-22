from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from api.app.data.preprocess import (
    export_es_pipeline,
    prepare_pipeline,
    profiles_pipeline,
    splits_pipeline,
)


data_app = typer.Typer(help="MovieLens 100K data pipeline commands")


def _print_summary(summary: dict[str, Any]) -> None:
    for key, value in summary.items():
        if key == "hashes" and isinstance(value, dict):
            typer.echo("hashes:")
            for hash_name, hash_value in value.items():
                typer.echo(f"  {hash_name}: {hash_value}")
            continue
        typer.echo(f"{key}: {value}")


def prepare_data(
    *,
    dataset_dir: Path | None,
    output_dir: Path | None,
    test_holdout: int,
    top_genres_k: int,
    top_rated_k: int,
    recent_k: int,
) -> dict[str, Any]:
    return prepare_pipeline(
        dataset_dir=dataset_dir,
        output_dir=output_dir,
        test_holdout=test_holdout,
        top_genres_k=top_genres_k,
        top_rated_k=top_rated_k,
        recent_k=recent_k,
    )


def build_profiles(
    *,
    dataset_dir: Path | None,
    output_dir: Path | None,
    top_genres_k: int,
    top_rated_k: int,
    recent_k: int,
) -> dict[str, Any]:
    return profiles_pipeline(
        dataset_dir=dataset_dir,
        output_dir=output_dir,
        top_genres_k=top_genres_k,
        top_rated_k=top_rated_k,
        recent_k=recent_k,
    )


def build_splits(
    *,
    dataset_dir: Path | None,
    output_dir: Path | None,
    test_holdout: int,
) -> dict[str, Any]:
    return splits_pipeline(dataset_dir=dataset_dir, output_dir=output_dir, test_holdout=test_holdout)


def build_es_bulk(*, dataset_dir: Path | None, output_dir: Path | None) -> dict[str, Any]:
    return export_es_pipeline(dataset_dir=dataset_dir, output_dir=output_dir)


@data_app.command("prepare")
def data_prepare(
    dataset_dir: Path | None = typer.Option(None, help="Path to the MovieLens dataset directory"),
    output_dir: Path | None = typer.Option(None, help="Path for processed outputs"),
    test_holdout: int = typer.Option(10, min=1, help="Number of most recent interactions per user for test split"),
    top_genres_k: int = typer.Option(5, min=1, help="Top genres per user profile"),
    top_rated_k: int = typer.Option(10, min=1, help="Top rated movie IDs per user profile"),
    recent_k: int = typer.Option(10, min=1, help="Most recent movie IDs per user profile"),
) -> None:
    """Run full deterministic data pipeline."""

    summary = prepare_data(
        dataset_dir=dataset_dir,
        output_dir=output_dir,
        test_holdout=test_holdout,
        top_genres_k=top_genres_k,
        top_rated_k=top_rated_k,
        recent_k=recent_k,
    )
    _print_summary(summary)


@data_app.command("profiles")
def data_profiles(
    dataset_dir: Path | None = typer.Option(None, help="Path to the MovieLens dataset directory"),
    output_dir: Path | None = typer.Option(None, help="Path for processed outputs"),
    top_genres_k: int = typer.Option(5, min=1, help="Top genres per user profile"),
    top_rated_k: int = typer.Option(10, min=1, help="Top rated movie IDs per user profile"),
    recent_k: int = typer.Option(10, min=1, help="Most recent movie IDs per user profile"),
) -> None:
    """Generate user profile parquet output."""

    summary = build_profiles(
        dataset_dir=dataset_dir,
        output_dir=output_dir,
        top_genres_k=top_genres_k,
        top_rated_k=top_rated_k,
        recent_k=recent_k,
    )
    _print_summary(summary)


@data_app.command("splits")
def data_splits(
    dataset_dir: Path | None = typer.Option(None, help="Path to the MovieLens dataset directory"),
    output_dir: Path | None = typer.Option(None, help="Path for processed outputs"),
    test_holdout: int = typer.Option(10, min=1, help="Number of most recent interactions per user for test split"),
) -> None:
    """Generate train/test splits parquet output."""

    summary = build_splits(dataset_dir=dataset_dir, output_dir=output_dir, test_holdout=test_holdout)
    _print_summary(summary)


@data_app.command("export-es")
def data_export_es(
    dataset_dir: Path | None = typer.Option(None, help="Path to the MovieLens dataset directory"),
    output_dir: Path | None = typer.Option(None, help="Path for processed outputs"),
) -> None:
    """Generate Elasticsearch baseline bulk JSONL for movies."""

    summary = build_es_bulk(dataset_dir=dataset_dir, output_dir=output_dir)
    _print_summary(summary)
