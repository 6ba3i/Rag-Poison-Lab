from __future__ import annotations

from pathlib import Path

import typer
import yaml

from api.app.llm.model_catalog import dump_catalog_json, refresh_cloud_model_catalog, write_cloud_model_catalog
from api.app.settings import get_settings

llm_app = typer.Typer(help="LLM catalog commands")


@llm_app.command("refresh-models")
def refresh_models_command(
    provider: list[str] = typer.Option(None, "--provider", help="Refresh only the given provider(s)."),
    output: Path | None = typer.Option(None, "--output", help="Override the target YAML path."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print the refreshed catalog without writing files."),
) -> None:
    """Refresh the curated cloud model catalog from official provider APIs."""

    settings = get_settings()
    catalog = refresh_cloud_model_catalog(settings=settings, providers=provider or None)

    if dry_run:
        typer.echo(dump_catalog_json(catalog).rstrip())
        return

    destination = output.resolve() if output is not None else settings.resolved_llm_models_path
    existing = _load_existing_catalog(destination)
    merged = {**existing, **catalog}
    write_cloud_model_catalog(path=destination, catalog=merged)
    typer.echo(f"Refreshed {destination}")


def _load_existing_catalog(path: Path) -> dict[str, list[str]]:
    if not path.exists() or not path.is_file():
        return {}
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        return {}
    existing: dict[str, list[str]] = {}
    for provider, value in parsed.items():
        if not isinstance(provider, str) or not isinstance(value, list):
            continue
        existing[provider] = [str(item).strip() for item in value if str(item).strip()]
    return existing
