from __future__ import annotations

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

    summary: dict[str, Any] = {
        "attack_type": config.attack_type,
        "poison_fraction": config.poison_fraction,
        "total_docs": total_docs,
        "poisoned_docs": poisoned_count,
        "source_path": str(source_path),
        "output_path": str(output_path),
        "attack_config_path": str(config_path),
    }
    if config.target_movie_id is not None:
        summary["target_movie_id"] = int(config.target_movie_id)

    return summary


def _resolve_attack_config_path(attack_config_path: Path | None) -> Path:
    if attack_config_path is not None:
        return attack_config_path.resolve()
    return (REPO_ROOT / "data" / "config" / "attack_config.json").resolve()
