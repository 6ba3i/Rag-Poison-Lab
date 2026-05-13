from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from agent.datasets.poison_builder import build_poisoned_bulk
from api.app.llm.registry import LlmRegistry
from api.app.settings import get_settings

attack_app = typer.Typer(help="Attack dataset commands")


def build_poisoned(
    *,
    processed_dir: Path | None,
    attack_config: Path | None,
) -> dict[str, Any]:
    # Ensure attacker provider/model config is resolvable early when model-tied generation is enabled.
    # The builder will still instantiate the concrete provider client per run.
    LlmRegistry(settings=get_settings())
    return build_poisoned_bulk(
        processed_dir=processed_dir,
        attack_config_path=attack_config,
    )


def _print_summary(summary: dict[str, Any]) -> None:
    for key, value in summary.items():
        typer.echo(f"{key}: {value}")


@attack_app.command("build-poisoned")
def attack_build_poisoned(
    processed_dir: Path | None = typer.Option(None, help="Path to processed data directory"),
    attack_config: Path | None = typer.Option(None, help="Path to attack config JSON"),
) -> None:
    """Build poisoned ES bulk from baseline bulk and attack configuration."""

    summary = build_poisoned(processed_dir=processed_dir, attack_config=attack_config)
    _print_summary(summary)
