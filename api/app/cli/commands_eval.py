from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import typer

from api.app.eval.audit import generate_audit_artifacts
from api.app.eval.runner import EvalMode, run_experiments
from api.app.settings import Settings


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
    overwrite: bool,
    settings: Settings | None = None,
    es_client: Any | None = None,
    attack_config: Path | None = None,
) -> dict[str, Any]:
    return run_experiments(
        mode=mode,
        label=label,
        k=k,
        user_id=user_id,
        batch_size=batch_size,
        settings=settings,
        es_client=es_client,
        results_root=results_root.resolve() if results_root is not None else None,
        allow_overwrite=overwrite,
        attack_config_path=attack_config.resolve() if attack_config is not None else None,
    )


def audit_run(
    *,
    label: str | None,
    run_dir: Path | None,
    user_id: int | None,
    results_root: Path | None,
) -> dict[str, Any]:
    return generate_audit_artifacts(
        label=label,
        run_dir=run_dir.resolve() if run_dir is not None else None,
        user_id=user_id,
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
    attack_config: Path | None = typer.Option(None, help="Path to attack config JSON"),
    overwrite: bool = typer.Option(False, "--overwrite", help="Allow overwriting an existing run label"),
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
            overwrite=overwrite,
            attack_config=attack_config,
        )
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Evaluation failed: {exc}")
        raise typer.Exit(code=1) from exc

    _print_summary(summary)


@eval_app.command("audit")
def eval_audit(
    label: str | None = typer.Option(None, help="Run label to audit (default: latest run)"),
    run_dir: Path | None = typer.Option(None, help="Explicit run directory path to audit"),
    user_id: int | None = typer.Option(None, help="User ID to audit retrieval/ranking flow"),
    results_root: Path | None = typer.Option(None, help="Override data/results/runs base path"),
) -> None:
    """Generate proof-led audit artifacts for poisoning, retrieval, and metrics behavior."""

    try:
        summary = audit_run(
            label=label,
            run_dir=run_dir,
            user_id=user_id,
            results_root=results_root,
        )
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Audit generation failed: {exc}")
        raise typer.Exit(code=1) from exc

    _print_summary(summary)
