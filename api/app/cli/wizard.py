from __future__ import annotations

from pathlib import Path

import questionary
import typer

from api.app.cli.commands_data import build_es_bulk, build_profiles, build_splits, prepare_data
from api.app.data.paths import resolve_default_dataset_dir, resolve_default_processed_dir


def _prompt_path(message: str, default_path: Path) -> Path:
    raw = questionary.text(message, default=str(default_path)).ask()
    return Path(raw or str(default_path)).resolve()


def _prompt_int(message: str, default: int, minimum: int = 1) -> int:
    raw = questionary.text(message, default=str(default)).ask()
    value = int(raw) if raw is not None else default
    if value < minimum:
        raise ValueError(f"Value must be >= {minimum}")
    return value


def run_wizard() -> None:
    typer.echo("Data Pipeline Wizard")

    while True:
        choice = questionary.select(
            "Select action",
            choices=[
                "prepare",
                "profiles",
                "splits",
                "export-es",
                "exit",
            ],
        ).ask()

        if choice in {None, "exit"}:
            typer.echo("Wizard exited")
            return

        try:
            dataset_dir = _prompt_path("Dataset directory", resolve_default_dataset_dir())
            output_dir = _prompt_path("Output directory", resolve_default_processed_dir())

            if choice == "prepare":
                test_holdout = _prompt_int("Test holdout (last N ratings per user)", 10)
                top_genres_k = _prompt_int("Top genres per user", 5)
                top_rated_k = _prompt_int("Top rated movie IDs per user", 10)
                recent_k = _prompt_int("Recent movie IDs per user", 10)
                summary = prepare_data(
                    dataset_dir=dataset_dir,
                    output_dir=output_dir,
                    test_holdout=test_holdout,
                    top_genres_k=top_genres_k,
                    top_rated_k=top_rated_k,
                    recent_k=recent_k,
                )
            elif choice == "profiles":
                top_genres_k = _prompt_int("Top genres per user", 5)
                top_rated_k = _prompt_int("Top rated movie IDs per user", 10)
                recent_k = _prompt_int("Recent movie IDs per user", 10)
                summary = build_profiles(
                    dataset_dir=dataset_dir,
                    output_dir=output_dir,
                    top_genres_k=top_genres_k,
                    top_rated_k=top_rated_k,
                    recent_k=recent_k,
                )
            elif choice == "splits":
                test_holdout = _prompt_int("Test holdout (last N ratings per user)", 10)
                summary = build_splits(
                    dataset_dir=dataset_dir,
                    output_dir=output_dir,
                    test_holdout=test_holdout,
                )
            else:
                summary = build_es_bulk(dataset_dir=dataset_dir, output_dir=output_dir)

            typer.echo("Action completed")
            for key, value in summary.items():
                typer.echo(f"{key}: {value}")
        except Exception as exc:  # pragma: no cover - wizard UX path
            typer.echo(f"Action failed: {exc}")
