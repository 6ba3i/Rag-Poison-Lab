from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from agent.attacks.poison_index import apply_poisoning
from agent.datasets.bulk_writer import read_bulk_movies, write_poisoned_bulk
from api.app.data.paths import (
    ES_BULK_MOVIES_JSONL,
    ES_BULK_POISONED_MOVIES_JSONL,
    REPO_ROOT,
    resolve_output_dir,
)
from common.schemas.attack_config import load_attack_config

POISONED_BULK_META_JSON = "es_bulk_poisoned_movies.meta.json"


def build_poisoned_bulk(
    *,
    processed_dir: Path | None = None,
    attack_config_path: Path | None = None,
) -> dict[str, Any]:
    processed_path = resolve_output_dir(processed_dir, create=False)
    source_path = processed_path / ES_BULK_MOVIES_JSONL
    output_path = processed_path / ES_BULK_POISONED_MOVIES_JSONL
    config_path = _resolve_attack_config_path(attack_config_path)

    config = load_attack_config(config_path)
    baseline_docs = read_bulk_movies(source_path, expected_index="movies")
    poisoned_docs = apply_poisoning(baseline_docs, config)
    total_docs = write_poisoned_bulk(output_path, poisoned_docs)
    poisoned_count = sum(1 for doc in poisoned_docs if bool(doc.get("poison_marker", False)))
    meta_path = processed_path / POISONED_BULK_META_JSON
    metadata = {
        "attack_type": config.attack_type,
        "poison_fraction": float(config.poison_fraction),
        "target_movie_id": int(config.target_movie_id) if config.target_movie_id is not None else None,
        "attack_config_sha256": _hash_file(config_path),
        "source_bulk_sha256": _hash_file(source_path),
        "output_bulk_sha256": _hash_file(output_path),
        "total_docs": int(total_docs),
        "poisoned_docs": int(poisoned_count),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    meta_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary: dict[str, Any] = {
        "attack_type": config.attack_type,
        "poison_fraction": config.poison_fraction,
        "total_docs": total_docs,
        "poisoned_docs": poisoned_count,
        "source_path": str(source_path),
        "output_path": str(output_path),
        "meta_path": str(meta_path),
        "attack_config_path": str(config_path),
    }
    if config.target_movie_id is not None:
        summary["target_movie_id"] = int(config.target_movie_id)

    return summary


def ensure_poisoned_bulk_fresh(
    *,
    processed_dir: Path | None = None,
    attack_config_path: Path | None = None,
) -> dict[str, Any]:
    processed_path = resolve_output_dir(processed_dir, create=False)
    source_path = processed_path / ES_BULK_MOVIES_JSONL
    output_path = processed_path / ES_BULK_POISONED_MOVIES_JSONL
    meta_path = processed_path / POISONED_BULK_META_JSON
    config_path = _resolve_attack_config_path(attack_config_path)

    if not source_path.exists() or source_path.stat().st_size == 0:
        raise FileNotFoundError(
            f"Baseline bulk is missing or empty: {source_path}. "
            "Run data prepare/export before building poisoned bulk."
        )
    if not config_path.exists() or config_path.stat().st_size == 0:
        raise FileNotFoundError(
            f"Attack config is missing or empty: {config_path}. "
            "Configure attack before building poisoned bulk."
        )

    reason = _poisoned_bulk_status_reason(
        source_path=source_path,
        output_path=output_path,
        meta_path=meta_path,
        config_path=config_path,
    )

    if reason == "up_to_date":
        return {
            "rebuilt": False,
            "reason": reason,
            "source_path": str(source_path),
            "output_path": str(output_path),
            "meta_path": str(meta_path),
            "attack_config_path": str(config_path),
        }

    build_summary = build_poisoned_bulk(processed_dir=processed_path, attack_config_path=config_path)
    return {
        "rebuilt": True,
        "reason": reason,
        "build_summary": build_summary,
        "source_path": str(source_path),
        "output_path": str(output_path),
        "meta_path": str(meta_path),
        "attack_config_path": str(config_path),
    }


def _resolve_attack_config_path(attack_config_path: Path | None) -> Path:
    if attack_config_path is not None:
        return attack_config_path.resolve()
    return (REPO_ROOT / "data" / "config" / "attack_config.json").resolve()


def _poisoned_bulk_status_reason(
    *,
    source_path: Path,
    output_path: Path,
    meta_path: Path,
    config_path: Path,
) -> str:
    if not output_path.exists() or output_path.stat().st_size == 0:
        return "missing_poisoned_bulk"

    metadata = _load_meta(meta_path)
    if metadata is None:
        return "missing_or_invalid_meta"

    if metadata.get("attack_config_sha256") != _hash_file(config_path):
        return "attack_config_changed"
    if metadata.get("source_bulk_sha256") != _hash_file(source_path):
        return "source_bulk_changed"
    return "up_to_date"


def _load_meta(path: Path) -> dict[str, Any] | None:
    if not path.exists() or path.stat().st_size == 0:
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _hash_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()
