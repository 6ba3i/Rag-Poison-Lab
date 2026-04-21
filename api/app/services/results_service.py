from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from api.app.settings import Settings


def list_runs(*, settings: Settings, limit: int, cursor: str | None) -> dict[str, Any]:
    root = _results_root(settings=settings)
    if not root.exists() or not root.is_dir():
        return {"items": [], "next_cursor": None, "total": 0}

    start = _parse_cursor(cursor)
    run_dirs = sorted(
        [entry for entry in root.iterdir() if entry.is_dir()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    total = len(run_dirs)
    if start >= total:
        return {"items": [], "next_cursor": None, "total": total}

    selected = run_dirs[start : start + limit]
    items = [_build_run_summary(run_dir=run_dir) for run_dir in selected]
    next_index = start + len(selected)
    next_cursor = str(next_index) if next_index < total else None
    return {"items": items, "next_cursor": next_cursor, "total": total}


def get_run_detail(*, settings: Settings, label: str) -> dict[str, Any]:
    run_dir = (_results_root(settings=settings) / label).resolve()
    root = _results_root(settings=settings).resolve()

    if root not in run_dir.parents:
        raise FileNotFoundError(f"Run '{label}' not found")
    if not run_dir.exists() or not run_dir.is_dir():
        raise FileNotFoundError(f"Run '{label}' not found")

    metrics = _read_json_object(run_dir / "metrics.json")
    manifest = _read_json_object(run_dir / "experiment_manifest.json")

    warnings_raw = metrics.get("warnings", []) if isinstance(metrics, dict) else []
    warnings = [str(item) for item in warnings_raw] if isinstance(warnings_raw, list) else []

    per_user_raw = metrics.get("per_user", []) if isinstance(metrics, dict) else []
    per_user = [item for item in per_user_raw if isinstance(item, dict)] if isinstance(per_user_raw, list) else []

    detail = {
        "summary": _build_run_summary(run_dir=run_dir, metrics=metrics, manifest=manifest),
        "warnings": warnings,
        "metadata": metrics.get("metadata") if isinstance(metrics.get("metadata"), dict) else None,
        "target_retrieval": metrics.get("target_retrieval") if isinstance(metrics.get("target_retrieval"), dict) else None,
        "repeat_stats": metrics.get("repeat_stats") if isinstance(metrics.get("repeat_stats"), dict) else None,
        "per_user": per_user,
        "manifest": manifest if manifest else None,
        "artifacts": _artifact_paths(run_dir=run_dir),
    }
    return detail


def _results_root(*, settings: Settings) -> Path:
    return (settings.resolved_data_root / "results" / "runs").resolve()


def _parse_cursor(cursor: str | None) -> int:
    if cursor is None or cursor.strip() == "":
        return 0
    try:
        value = int(cursor)
    except ValueError as exc:
        raise ValueError("cursor must be an integer offset") from exc
    if value < 0:
        raise ValueError("cursor must be non-negative")
    return value


def _build_run_summary(
    *,
    run_dir: Path,
    metrics: dict[str, Any] | None = None,
    manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metrics_payload = metrics if metrics is not None else _read_json_object(run_dir / "metrics.json")
    manifest_payload = manifest if manifest is not None else _read_json_object(run_dir / "experiment_manifest.json")

    generated_at_utc = _first_nonempty(
        _as_str(_nested(metrics_payload, "metadata", "generated_at_utc")),
        _as_str(manifest_payload.get("generated_at_utc")),
    )

    mode = _first_nonempty(
        _as_str(metrics_payload.get("mode")),
        _as_str(manifest_payload.get("mode")),
    )

    summary = {
        "label": run_dir.name,
        "generated_at_utc": generated_at_utc,
        "mode": mode,
        "k": _first_int(metrics_payload.get("k"), manifest_payload.get("k")),
        "requested_users": _first_int(metrics_payload.get("requested_users"), manifest_payload.get("requested_users")),
        "evaluated_users": _first_int(metrics_payload.get("evaluated_users"), manifest_payload.get("evaluated_users")),
        "skipped_users": _first_int(metrics_payload.get("skipped_users"), manifest_payload.get("skipped_users")),
        "target_movie_id": _first_int(
            _nested(metrics_payload, "metadata", "target_movie_id"),
            _nested(metrics_payload, "target_retrieval", "target_movie_id"),
        ),
        "baseline": _to_metric_map(metrics_payload.get("baseline")),
        "attacked": _to_metric_map(metrics_payload.get("attacked")),
        "delta": _to_metric_map(metrics_payload.get("delta")),
        "defended": _to_metric_map(metrics_payload.get("defended")),
        "defense_delta": _to_metric_map(metrics_payload.get("defense_delta")),
        "warnings_count": _warnings_count(metrics_payload),
        "repeat_count": _first_int(
            _nested(metrics_payload, "metadata", "repeat_count"),
            manifest_payload.get("repeat_count"),
        )
        or 1,
        "has_metrics": (run_dir / "metrics.json").exists(),
        "has_manifest": (run_dir / "experiment_manifest.json").exists(),
        "has_attack_trace": (run_dir / "attack_trace.json").exists(),
        "has_summary": (run_dir / "summary.md").exists(),
        "has_delta_csv": (run_dir / "delta.csv").exists(),
    }
    return summary


def _warnings_count(metrics_payload: dict[str, Any]) -> int:
    warnings = metrics_payload.get("warnings")
    if isinstance(warnings, list):
        return len(warnings)
    return 0


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file() or path.stat().st_size == 0:
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _to_metric_map(value: object) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    output: dict[str, float] = {}
    for key, item in value.items():
        try:
            output[str(key)] = round(float(item), 6)
        except Exception:  # noqa: BLE001
            continue
    return output


def _artifact_paths(*, run_dir: Path) -> dict[str, str | None]:
    return {
        "run_dir": str(run_dir),
        "metrics_path": _existing_path(run_dir / "metrics.json"),
        "manifest_path": _existing_path(run_dir / "experiment_manifest.json"),
        "attack_trace_path": _existing_path(run_dir / "attack_trace.json"),
        "summary_path": _existing_path(run_dir / "summary.md"),
        "delta_csv_path": _existing_path(run_dir / "delta.csv"),
        "llm_runtime_path": _existing_path(run_dir / "llm_config.runtime.json"),
        "attack_runtime_path": _existing_path(run_dir / "attack_config.runtime.json"),
        "defense_runtime_path": _existing_path(run_dir / "defense_config.runtime.json"),
        "llm_snapshot_path": _existing_path(run_dir / "llm_config.snapshot.json"),
        "attack_snapshot_path": _existing_path(run_dir / "attack_config.snapshot.json"),
        "defense_snapshot_path": _existing_path(run_dir / "defense_config.snapshot.json"),
    }


def _existing_path(path: Path) -> str | None:
    return str(path) if path.exists() and path.is_file() else None


def _nested(payload: dict[str, Any], key: str, nested_key: str) -> Any | None:
    value = payload.get(key)
    if isinstance(value, dict):
        return value.get(nested_key)
    return None


def _first_int(*values: object) -> int | None:
    for value in values:
        if value is None:
            continue
        try:
            return int(value)
        except Exception:  # noqa: BLE001
            continue
    return None


def _first_nonempty(*values: str | None) -> str | None:
    for value in values:
        if value is not None and value.strip() != "":
            return value
    return None


def _as_str(value: object) -> str | None:
    if value is None:
        return None
    rendered = str(value)
    return rendered if rendered.strip() != "" else None
