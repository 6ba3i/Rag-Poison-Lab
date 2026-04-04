from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from agent.datasets.poison_builder import ensure_poisoned_bulk_fresh
from api.app.cli.commands_attack import build_poisoned
from api.app.data.paths import ES_BULK_MOVIES_JSONL, ES_BULK_POISONED_MOVIES_JSONL, resolve_default_processed_dir
from api.app.services.indexing_service import (
    get_index_stats,
    index_baseline_direct,
    index_poisoned_direct,
    reset_indices,
)


index_app = typer.Typer(help="Elasticsearch indexing commands")


def _print_summary(summary: dict[str, Any], *, prefix: str = "") -> None:
    for key, value in summary.items():
        if isinstance(value, dict):
            typer.echo(f"{prefix}{key}:")
            _print_summary(value, prefix=prefix + "  ")
            continue
        typer.echo(f"{prefix}{key}: {value}")


def _resolve_path(path: Path | None) -> Path | None:
    if path is None:
        return None
    return path.resolve()


def index_baseline(*, es_url: str | None = None, processed_dir: Path | None = None) -> dict[str, Any]:
    processed_path = _resolve_path(processed_dir)
    provenance: dict[str, Any] = {}
    if processed_path is not None:
        provenance["source_bulk_path"] = str((processed_path / ES_BULK_MOVIES_JSONL).resolve())
    return index_baseline_direct(es_url=es_url, processed_dir=processed_path, provenance=provenance)


def index_poisoned(
    *,
    es_url: str | None = None,
    processed_dir: Path | None = None,
    attack_config: Path | None = None,
    build_if_missing: bool = False,
) -> dict[str, Any]:
    processed_path = _resolve_path(processed_dir)
    refresh = ensure_poisoned_bulk_fresh(
        processed_dir=processed_path,
        attack_config_path=_resolve_path(attack_config),
    )
    if build_if_missing:
        # Backward-compatible behavior: callers using --build-if-missing
        # still get a harmless no-op path when the file is already fresh.
        _build_poisoned_if_missing(processed_dir=processed_path, attack_config=attack_config)
    poisoned_meta = _read_poisoned_meta(processed_dir=processed_path)
    indexed = index_poisoned_direct(
        es_url=es_url,
        processed_dir=processed_path,
        provenance=_poisoned_index_provenance(poisoned_meta),
    )
    return {
        "poisoned_bulk_refresh": refresh,
        "poisoned_bulk_meta": poisoned_meta,
        "indexing": indexed,
    }


def index_both(
    *,
    es_url: str | None = None,
    processed_dir: Path | None = None,
    attack_config: Path | None = None,
    build_poisoned_if_missing: bool = False,
) -> dict[str, Any]:
    baseline = index_baseline(es_url=es_url, processed_dir=processed_dir)
    poisoned = index_poisoned(
        es_url=es_url,
        processed_dir=processed_dir,
        attack_config=attack_config,
        build_if_missing=build_poisoned_if_missing,
    )
    stats = index_stats(es_url=es_url)
    return {
        "baseline": baseline,
        "poisoned": poisoned,
        "stats": stats,
    }


def index_stats(*, es_url: str | None = None) -> dict[str, Any]:
    return get_index_stats(es_url=es_url)


def index_reset(*, es_url: str | None = None) -> dict[str, Any]:
    return reset_indices(es_url=es_url)


def _build_poisoned_if_missing(*, processed_dir: Path | None, attack_config: Path | None) -> dict[str, Any] | None:
    resolved_processed_dir = processed_dir or resolve_default_processed_dir()
    poisoned_path = resolved_processed_dir / ES_BULK_POISONED_MOVIES_JSONL
    if poisoned_path.exists() and poisoned_path.stat().st_size > 0:
        return None

    return build_poisoned(processed_dir=resolved_processed_dir, attack_config=_resolve_path(attack_config))


def _read_poisoned_meta(*, processed_dir: Path | None) -> dict[str, Any]:
    resolved_processed_dir = processed_dir or resolve_default_processed_dir()
    meta_path = resolved_processed_dir / "es_bulk_poisoned_movies.meta.json"
    if not meta_path.exists() or meta_path.stat().st_size == 0:
        return {"meta_path": str(meta_path), "available": False}
    try:
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"meta_path": str(meta_path), "available": False, "error": str(exc)}
    if not isinstance(payload, dict):
        return {"meta_path": str(meta_path), "available": False, "error": "meta payload is not an object"}
    payload["meta_path"] = str(meta_path)
    payload["available"] = True
    return payload


def _poisoned_index_provenance(meta: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "attack_type",
        "poison_fraction",
        "target_movie_id",
        "attack_config_sha256",
        "source_bulk_sha256",
        "output_bulk_sha256",
        "generated_at_utc",
        "total_docs",
        "poisoned_docs",
    )
    output: dict[str, Any] = {}
    for key in keys:
        if key in meta:
            output[key] = meta[key]
    if "meta_path" in meta:
        output["poisoned_bulk_meta_path"] = meta["meta_path"]
    return output


@index_app.command("baseline")
def index_baseline_command(
    es_url: str | None = typer.Option(None, help="Elasticsearch base URL"),
    processed_dir: Path | None = typer.Option(None, help="Path to processed data directory"),
) -> None:
    """Index baseline movies into Elasticsearch index `movies`."""

    summary = index_baseline(es_url=es_url, processed_dir=processed_dir)
    _print_summary(summary)


@index_app.command("poisoned")
def index_poisoned_command(
    es_url: str | None = typer.Option(None, help="Elasticsearch base URL"),
    processed_dir: Path | None = typer.Option(None, help="Path to processed data directory"),
    attack_config: Path | None = typer.Option(None, help="Path to attack config JSON"),
    build_if_missing: bool = typer.Option(
        False,
        "--build-if-missing",
        help="Deprecated compatibility flag. Poisoned bulk is now auto-refreshed when stale.",
    ),
) -> None:
    """Index poisoned movies into Elasticsearch index `movies_poisoned`."""

    summary = index_poisoned(
        es_url=es_url,
        processed_dir=processed_dir,
        attack_config=attack_config,
        build_if_missing=build_if_missing,
    )
    _print_summary(summary)


@index_app.command("both")
def index_both_command(
    es_url: str | None = typer.Option(None, help="Elasticsearch base URL"),
    processed_dir: Path | None = typer.Option(None, help="Path to processed data directory"),
    attack_config: Path | None = typer.Option(None, help="Path to attack config JSON"),
    build_if_missing: bool = typer.Option(
        False,
        "--build-if-missing",
        help="Deprecated compatibility flag. Poisoned bulk is now auto-refreshed when stale.",
    ),
) -> None:
    """Index baseline and poisoned datasets, then print index stats."""

    summary = index_both(
        es_url=es_url,
        processed_dir=processed_dir,
        attack_config=attack_config,
        build_poisoned_if_missing=build_if_missing,
    )
    _print_summary(summary)


@index_app.command("stats")
def index_stats_command(
    es_url: str | None = typer.Option(None, help="Elasticsearch base URL"),
) -> None:
    """Show index existence and document counts."""

    summary = index_stats(es_url=es_url)
    _print_summary(summary)


@index_app.command("reset")
def index_reset_command(
    es_url: str | None = typer.Option(None, help="Elasticsearch base URL"),
    yes: bool = typer.Option(False, "--yes", help="Confirm deleting `movies` and `movies_poisoned` indices"),
) -> None:
    """Delete baseline and poisoned indices."""

    if not yes:
        typer.echo("Refusing to reset indices without --yes")
        raise typer.Exit(code=1)

    summary = index_reset(es_url=es_url)
    _print_summary(summary)
