from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import typer

from api.app.eval.runner import EvalMode, run_experiments


eval_app = typer.Typer(help="Evaluation commands")


def _print_summary(summary: dict[str, Any], *, prefix: str = "") -> None:
    for key, value in summary.items():
        if isinstance(value, dict):
            typer.echo(f"{prefix}{key}:")
            _print_summary(value, prefix=prefix + "  ")
            continue
        typer.echo(f"{prefix}{key}: {value}")


def evaluate_run(
    *,
    mode: EvalMode,
    label: str | None,
    k: int,
    user_id: int | None,
    batch_size: int,
    results_root: Path | None,
) -> dict[str, Any]:
    return run_experiments(
        mode=mode,
        label=label,
        k=k,
        user_id=user_id,
        batch_size=batch_size,
        results_root=results_root.resolve() if results_root is not None else None,
    )


@eval_app.command("run")
def eval_run(
    mode: Literal["single", "batch", "full"] = typer.Option("single", help="Evaluation mode"),
    label: str | None = typer.Option(None, help="Run label (default: timestamped)"),
    k: int = typer.Option(10, min=1, help="Top-K cutoff for metrics"),
    user_id: int | None = typer.Option(None, help="User ID when mode=single"),
    batch_size: int = typer.Option(100, min=1, help="Number of users when mode=batch"),
    results_root: Path | None = typer.Option(None, help="Override data/results/runs base path"),
) -> None:
    """Run baseline vs attacked evaluation and write metrics artifacts."""

    try:
        summary = evaluate_run(
            mode=mode,
            label=label,
            k=k,
            user_id=user_id,
            batch_size=batch_size,
            results_root=results_root,
        )
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Evaluation failed: {exc}")
        raise typer.Exit(code=1) from exc

    _print_summary(summary)
