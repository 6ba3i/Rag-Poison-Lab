from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import typer

from api.app.services.orchestration_service import ExperimentOrchestrator, ExperimentRunOptions

experiment_app = typer.Typer(help="End-to-end experiment orchestration")


def _print_summary(summary: dict[str, Any], *, prefix: str = "") -> None:
    for key, value in summary.items():
        if isinstance(value, dict):
            typer.echo(f"{prefix}{key}:")
            _print_summary(value, prefix=prefix + "  ")
            continue
        typer.echo(f"{prefix}{key}: {value}")


@experiment_app.command("run")
def experiment_run(
    label: str | None = typer.Option(None, help="Run label (default: timestamped)"),
    mode: Literal["single", "batch", "full"] = typer.Option("single", help="Evaluation mode"),
    run_profile: Literal["pipeline", "single_demo"] = typer.Option(
        "pipeline",
        help="Run profile semantic defaults. single_demo requires mode=single.",
    ),
    k: int = typer.Option(10, min=1, help="Top-K cutoff for metrics"),
    user_id: int | None = typer.Option(None, help="User ID when mode=single"),
    batch_size: int = typer.Option(100, min=1, help="Number of users when mode=batch"),
    run_prepare: bool | None = typer.Option(None, help="Override: run data prepare before indexing"),
    run_index: bool | None = typer.Option(None, help="Override: run baseline+poisoned indexing"),
    run_eval: bool | None = typer.Option(None, help="Override: run evaluation"),
    run_report: bool | None = typer.Option(None, help="Override: generate report artifacts"),
    overwrite: bool = typer.Option(False, "--overwrite", help="Allow overwriting an existing run label"),
    dataset_dir: Path | None = typer.Option(None, help="Path to MovieLens dataset directory"),
    output_dir: Path | None = typer.Option(None, help="Path to processed output directory"),
    es_url: str | None = typer.Option(None, help="Elasticsearch URL"),
    attack_config: Path | None = typer.Option(None, help="Path to attack config JSON"),
) -> None:
    orchestrator = ExperimentOrchestrator()
    summary = orchestrator.run(
        options=ExperimentRunOptions(
            label=label,
            mode=mode,
            k=k,
            user_id=user_id,
            batch_size=batch_size,
            run_profile=run_profile,
            run_prepare=run_prepare,
            run_index=run_index,
            run_eval=run_eval,
            run_report=run_report,
            overwrite=overwrite,
            dataset_dir=dataset_dir.resolve() if dataset_dir is not None else None,
            output_dir=output_dir.resolve() if output_dir is not None else None,
            es_url=es_url,
            attack_config=attack_config.resolve() if attack_config is not None else None,
        )
    )
    _print_summary(summary)
