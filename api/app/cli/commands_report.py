from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from api.app.eval.reporting import generate_reports


report_app = typer.Typer(help="Reporting commands")


def _print_summary(summary: dict[str, Any], *, prefix: str = "") -> None:
    for key, value in summary.items():
        if isinstance(value, dict):
            typer.echo(f"{prefix}{key}:")
            _print_summary(value, prefix=prefix + "  ")
            continue
        typer.echo(f"{prefix}{key}: {value}")


def generate_report_artifacts(
    *,
    label: str | None,
    run_dir: Path | None,
    results_root: Path | None,
) -> dict[str, Any]:
    return generate_reports(
        label=label,
        run_dir=run_dir.resolve() if run_dir is not None else None,
        results_root=results_root.resolve() if results_root is not None else None,
    )


@report_app.command("generate")
def report_generate(
    label: str | None = typer.Option(None, help="Run label under data/results/runs"),
    run_dir: Path | None = typer.Option(None, help="Explicit run directory path"),
    results_root: Path | None = typer.Option(None, help="Override data/results/runs base path"),
) -> None:
    """Generate summary.md, delta.csv, and config snapshots for a run."""

    if label is None and run_dir is None:
        typer.echo("Provide --label or --run-dir")
        raise typer.Exit(code=1)

    try:
        summary = generate_report_artifacts(label=label, run_dir=run_dir, results_root=results_root)
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Report generation failed: {exc}")
        raise typer.Exit(code=1) from exc

    _print_summary(summary)
