from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from api.app.eval.runner import resolve_run_dir
from api.app.settings import Settings, get_settings
from common.schemas.attack_config import default_attack_config, load_attack_config
from common.schemas.defense_config import default_defense_config, load_defense_config
from common.schemas.llm_config import LlmConfig, default_llm_config


def generate_reports(
    *,
    label: str | None = None,
    run_dir: Path | None = None,
    settings: Settings | None = None,
    results_root: Path | None = None,
) -> dict[str, Any]:
    resolved_settings = settings or get_settings()

    if run_dir is None:
        if label is None:
            raise ValueError("Provide either label or run_dir")
        resolved_run_dir = resolve_run_dir(settings=resolved_settings, label=label, results_root=results_root)
    else:
        resolved_run_dir = run_dir.resolve()

    if not resolved_run_dir.exists() or not resolved_run_dir.is_dir():
        raise FileNotFoundError(f"Run directory not found: {resolved_run_dir}")

    metrics_path = resolved_run_dir / "metrics.json"
    if not metrics_path.exists() or metrics_path.stat().st_size == 0:
        raise FileNotFoundError(f"metrics.json not found in run directory: {resolved_run_dir}")

    payload = _load_json_object(metrics_path)
    baseline = _float_map(payload.get("baseline", {}))
    attacked = _float_map(payload.get("attacked", {}))
    delta = _float_map(payload.get("delta", {}))

    summary_path = resolved_run_dir / "summary.md"
    delta_csv_path = resolved_run_dir / "delta.csv"
    llm_snapshot_path = resolved_run_dir / "llm_config.snapshot.json"
    attack_snapshot_path = resolved_run_dir / "attack_config.snapshot.json"
    defense_snapshot_path = resolved_run_dir / "defense_config.snapshot.json"

    _write_summary(
        summary_path,
        payload=payload,
        baseline=baseline,
        attacked=attacked,
        delta=delta,
    )
    _write_delta_csv(delta_csv_path, baseline=baseline, attacked=attacked, delta=delta)
    _snapshot_configs(
        settings=resolved_settings,
        run_dir=resolved_run_dir,
        llm_snapshot_path=llm_snapshot_path,
        attack_snapshot_path=attack_snapshot_path,
        defense_snapshot_path=defense_snapshot_path,
    )

    return {
        "run_dir": str(resolved_run_dir),
        "metrics_path": str(metrics_path),
        "summary_path": str(summary_path),
        "delta_csv_path": str(delta_csv_path),
        "llm_config_snapshot_path": str(llm_snapshot_path),
        "attack_config_snapshot_path": str(attack_snapshot_path),
        "defense_config_snapshot_path": str(defense_snapshot_path),
    }


def list_run_labels(*, settings: Settings | None = None, results_root: Path | None = None) -> list[str]:
    resolved_settings = settings or get_settings()
    base = results_root.resolve() if results_root is not None else (resolved_settings.resolved_data_root / "results" / "runs")
    if not base.exists() or not base.is_dir():
        return []

    labels = [entry.name for entry in base.iterdir() if entry.is_dir()]
    return sorted(labels)


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Invalid JSON at {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def _float_map(raw: object) -> dict[str, float]:
    if not isinstance(raw, dict):
        return {}
    output: dict[str, float] = {}
    for key, value in raw.items():
        try:
            output[str(key)] = round(float(value), 6)
        except Exception:  # noqa: BLE001
            output[str(key)] = 0.0
    return output


def _write_summary(
    path: Path,
    *,
    payload: dict[str, Any],
    baseline: dict[str, float],
    attacked: dict[str, float],
    delta: dict[str, float],
) -> None:
    label = str(payload.get("label", path.parent.name))
    mode = str(payload.get("mode", "unknown"))
    k = int(payload.get("k", 10))
    requested = int(payload.get("requested_users", 0))
    evaluated = int(payload.get("evaluated_users", 0))
    skipped = int(payload.get("skipped_users", 0))
    target_movie_id = payload.get("metadata", {}).get("target_movie_id") if isinstance(payload.get("metadata"), dict) else None

    defended = _float_map(payload.get("defended", {}))
    defense_delta = _float_map(payload.get("defense_delta", {}))
    repeat_stats = payload.get("repeat_stats") if isinstance(payload.get("repeat_stats"), dict) else None

    keys = sorted(set(baseline.keys()) | set(attacked.keys()) | set(delta.keys()))
    if defended:
        keys = sorted(set(keys) | set(defended.keys()) | set(defense_delta.keys()))

    lines: list[str] = []
    lines.append(f"# Experiment Summary: {label}")
    lines.append("")
    lines.append(f"- mode: `{mode}`")
    lines.append(f"- k: `{k}`")
    lines.append(f"- requested_users: `{requested}`")
    lines.append(f"- evaluated_users: `{evaluated}`")
    lines.append(f"- skipped_users: `{skipped}`")
    lines.append(f"- target_movie_id: `{target_movie_id}`")
    lines.append(f"- repeat_count: `{payload.get('metadata', {}).get('repeat_count', 1) if isinstance(payload.get('metadata'), dict) else 1}`")
    lines.append("")
    if defended:
        lines.append("| metric | baseline | attacked | delta | defended | defense_delta |")
        lines.append("|---|---:|---:|---:|---:|---:|")
    else:
        lines.append("| metric | baseline | attacked | delta |")
        lines.append("|---|---:|---:|---:|")
    for key in keys:
        if defended:
            lines.append(
                f"| {key} | {baseline.get(key, 0.0):.6f} | {attacked.get(key, 0.0):.6f} | {delta.get(key, 0.0):.6f} | {defended.get(key, 0.0):.6f} | {defense_delta.get(key, 0.0):.6f} |"
            )
        else:
            lines.append(
                f"| {key} | {baseline.get(key, 0.0):.6f} | {attacked.get(key, 0.0):.6f} | {delta.get(key, 0.0):.6f} |"
            )

    if repeat_stats:
        lines.append("")
        lines.append("## Repeated-run statistics")
        repeat_count = int(repeat_stats.get("repeat_count", 0))
        lines.append(f"- repeats: `{repeat_count}`")
        delta_stats = repeat_stats.get("delta", {})
        if isinstance(delta_stats, dict):
            metrics = delta_stats.get("metrics", {})
            significance = delta_stats.get("significance", {})
            if isinstance(metrics, dict) and metrics:
                lines.append("")
                lines.append("| metric | mean | stddev | stderr | ci95_low | ci95_high | p_value |")
                lines.append("|---|---:|---:|---:|---:|---:|---:|")
                for key in sorted(metrics.keys()):
                    stat_row = metrics.get(key, {})
                    sig_row = significance.get(key, {}) if isinstance(significance, dict) else {}
                    if not isinstance(stat_row, dict):
                        continue
                    lines.append(
                        "| {key} | {mean} | {stddev} | {stderr} | {ci_low} | {ci_high} | {p_value} |".format(
                            key=key,
                            mean=_fmt_optional(stat_row.get("mean")),
                            stddev=_fmt_optional(stat_row.get("stddev")),
                            stderr=_fmt_optional(stat_row.get("stderr")),
                            ci_low=_fmt_optional(stat_row.get("ci95_low")),
                            ci_high=_fmt_optional(stat_row.get("ci95_high")),
                            p_value=_fmt_optional(sig_row.get("p_value")) if isinstance(sig_row, dict) else "-",
                        )
                    )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_delta_csv(
    path: Path,
    *,
    baseline: dict[str, float],
    attacked: dict[str, float],
    delta: dict[str, float],
) -> None:
    defended = {}
    defense_delta = {}
    parent_metrics = path.parent / "metrics.json"
    if parent_metrics.exists():
        payload = _load_json_object(parent_metrics)
        defended = _float_map(payload.get("defended", {}))
        defense_delta = _float_map(payload.get("defense_delta", {}))

    keys = sorted(set(baseline.keys()) | set(attacked.keys()) | set(delta.keys()) | set(defended.keys()) | set(defense_delta.keys()))

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        if defended:
            writer.writerow(["metric", "baseline", "attacked", "delta", "defended", "defense_delta"])
        else:
            writer.writerow(["metric", "baseline", "attacked", "delta"])
        for key in keys:
            row = [
                key,
                f"{baseline.get(key, 0.0):.6f}",
                f"{attacked.get(key, 0.0):.6f}",
                f"{delta.get(key, 0.0):.6f}",
            ]
            if defended:
                row.extend(
                    [
                        f"{defended.get(key, 0.0):.6f}",
                        f"{defense_delta.get(key, 0.0):.6f}",
                    ]
                )
            writer.writerow(row)


def _snapshot_configs(
    *,
    settings: Settings,
    run_dir: Path,
    llm_snapshot_path: Path,
    attack_snapshot_path: Path,
    defense_snapshot_path: Path,
) -> None:
    runtime_llm_path = run_dir / "llm_config.runtime.json"
    runtime_attack_path = run_dir / "attack_config.runtime.json"
    runtime_defense_path = run_dir / "defense_config.runtime.json"
    if runtime_llm_path.exists() and runtime_llm_path.stat().st_size > 0:
        llm_snapshot_path.write_text(runtime_llm_path.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        llm_snapshot_path.write_text(
            json.dumps(_load_llm_config_payload(settings), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if runtime_attack_path.exists() and runtime_attack_path.stat().st_size > 0:
        attack_snapshot_path.write_text(runtime_attack_path.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        attack_snapshot_path.write_text(
            json.dumps(_load_attack_config_payload(settings), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if runtime_defense_path.exists() and runtime_defense_path.stat().st_size > 0:
        defense_snapshot_path.write_text(runtime_defense_path.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        defense_snapshot_path.write_text(
            json.dumps(_load_defense_config_payload(settings), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _load_llm_config_payload(settings: Settings) -> dict[str, Any]:
    path = settings.resolved_llm_config_path
    if not path.exists() or path.stat().st_size == 0:
        config = default_llm_config()
        return config.model_dump()

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        config = LlmConfig.model_validate(raw)
        return config.model_dump()
    except Exception:  # noqa: BLE001
        config = default_llm_config()
        return config.model_dump()


def _load_attack_config_payload(settings: Settings) -> dict[str, Any]:
    path = settings.resolved_attack_config_path
    if not path.exists() or path.stat().st_size == 0:
        return default_attack_config().model_dump()

    try:
        config = load_attack_config(path)
        return config.model_dump()
    except Exception:  # noqa: BLE001
        return default_attack_config().model_dump()


def _load_defense_config_payload(settings: Settings) -> dict[str, Any]:
    path = settings.resolved_defense_config_path
    if not path.exists() or path.stat().st_size == 0:
        return default_defense_config().model_dump()

    try:
        config = load_defense_config(path)
        return config.model_dump()
    except Exception:  # noqa: BLE001
        return default_defense_config().model_dump()


def _fmt_optional(value: object) -> str:
    if isinstance(value, (int, float)):
        return f"{float(value):.6f}"
    return "-"
