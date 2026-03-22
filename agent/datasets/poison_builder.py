from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import logging
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
DIAGNOSTIC_SAMPLE_LIMIT = 10

logger = logging.getLogger(__name__)


def build_poisoned_bulk(
    *,
    processed_dir: Path | None = None,
    attack_config_path: Path | None = None,
) -> dict[str, Any]:
    processed_path = resolve_output_dir(processed_dir, create=False)
    source_path = processed_path / ES_BULK_MOVIES_JSONL
    output_path = processed_path / ES_BULK_POISONED_MOVIES_JSONL
    config_path = _resolve_attack_config_path(attack_config_path)

    logger.info(
        "poison_build_start phase=poison_build attack_config_path=%s source_path=%s output_path=%s",
        config_path,
        source_path,
        output_path,
    )
    config = load_attack_config(config_path)
    baseline_docs = read_bulk_movies(source_path, expected_index="movies")
    logger.info(
        "poison_config_resolved phase=poison_build attack_type=%s poison_fraction=%s target_movie_id=%s payload_text_len=%s keyword_count=%s",
        config.attack_type,
        config.poison_fraction,
        config.target_movie_id,
        len(config.payload_text.strip()),
        len(config.keyword_list),
    )
    poisoned_docs = apply_poisoning(baseline_docs, config)
    total_docs = write_poisoned_bulk(output_path, poisoned_docs)
    poisoned_count = sum(1 for doc in poisoned_docs if bool(doc.get("poison_marker", False)))
    diagnostics = _poison_diagnostics(
        baseline_docs=baseline_docs,
        poisoned_docs=poisoned_docs,
        target_movie_id=config.target_movie_id,
    )
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
        "diagnostics": diagnostics,
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
        "diagnostics": diagnostics,
    }
    if config.target_movie_id is not None:
        summary["target_movie_id"] = int(config.target_movie_id)

    logger.info(
        "poison_build_complete phase=poison_build attack_type=%s poison_fraction=%s total_docs=%s poisoned_docs=%s changed_title=%s changed_genres=%s changed_synopsis=%s changed_only_poison_fields=%s sample_poisoned_movie_ids=%s output_path=%s meta_path=%s",
        config.attack_type,
        config.poison_fraction,
        total_docs,
        poisoned_count,
        diagnostics["changed_title"],
        diagnostics["changed_genres"],
        diagnostics["changed_synopsis"],
        diagnostics["changed_only_poison_fields"],
        diagnostics["sample_poisoned_movie_ids"],
        output_path,
        meta_path,
    )
    if config.target_movie_id is not None and not diagnostics["target_is_poisoned"]:
        logger.warning(
            "poison_target_not_poisoned phase=poison_build attack_type=%s target_movie_id=%s poison_fraction=%s",
            config.attack_type,
            config.target_movie_id,
            config.poison_fraction,
        )

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
    logger.info(
        "poison_freshness_check phase=poison_build reason=%s source_path=%s output_path=%s meta_path=%s attack_config_path=%s",
        reason,
        source_path,
        output_path,
        meta_path,
        config_path,
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


def _poison_diagnostics(
    *,
    baseline_docs: list[dict[str, object]],
    poisoned_docs: list[dict[str, object]],
    target_movie_id: int | None,
) -> dict[str, Any]:
    baseline_by_id = {str(doc.get("movie_id", "")).strip(): doc for doc in baseline_docs}
    poisoned_by_id = {str(doc.get("movie_id", "")).strip(): doc for doc in poisoned_docs}

    changed_title = 0
    changed_genres = 0
    changed_synopsis = 0
    changed_only_poison_fields = 0
    changed_any_non_poison_fields = 0
    poisoned_movie_ids: list[int] = []
    modified_field_samples: list[dict[str, object]] = []

    for movie_id, poisoned_doc in poisoned_by_id.items():
        baseline_doc = baseline_by_id.get(movie_id, {})
        title_changed = str(baseline_doc.get("title", "") or "").strip() != str(poisoned_doc.get("title", "") or "").strip()
        genres_changed = _normalize_genres(baseline_doc.get("genres", [])) != _normalize_genres(poisoned_doc.get("genres", []))
        synopsis_changed = (
            str(baseline_doc.get("synopsis", "") or "").strip() != str(poisoned_doc.get("synopsis", "") or "").strip()
        )
        marker_changed = bool(baseline_doc.get("poison_marker", False)) != bool(poisoned_doc.get("poison_marker", False))
        payload_changed = (
            str(baseline_doc.get("poison_payload", "") or "").strip()
            != str(poisoned_doc.get("poison_payload", "") or "").strip()
        )

        if title_changed:
            changed_title += 1
        if genres_changed:
            changed_genres += 1
        if synopsis_changed:
            changed_synopsis += 1
        if title_changed or genres_changed or synopsis_changed:
            changed_any_non_poison_fields += 1
        elif marker_changed or payload_changed:
            changed_only_poison_fields += 1

        if bool(poisoned_doc.get("poison_marker", False)):
            try:
                poisoned_movie_ids.append(int(movie_id))
            except Exception:  # noqa: BLE001
                continue

        if (title_changed or genres_changed or synopsis_changed or marker_changed or payload_changed) and len(modified_field_samples) < DIAGNOSTIC_SAMPLE_LIMIT:
            modified_fields: list[str] = []
            if title_changed:
                modified_fields.append("title")
            if genres_changed:
                modified_fields.append("genres")
            if synopsis_changed:
                modified_fields.append("synopsis")
            if marker_changed:
                modified_fields.append("poison_marker")
            if payload_changed:
                modified_fields.append("poison_payload")
            modified_field_samples.append(
                {
                    "movie_id": movie_id,
                    "modified_fields": modified_fields,
                    "synopsis_before": str(baseline_doc.get("synopsis", "") or "").strip()[:120],
                    "synopsis_after": str(poisoned_doc.get("synopsis", "") or "").strip()[:120],
                    "poison_payload_after": str(poisoned_doc.get("poison_payload", "") or "").strip()[:120],
                }
            )

    target_doc = poisoned_by_id.get(str(target_movie_id)) if target_movie_id is not None else None
    target_is_poisoned = bool(target_doc and (target_doc.get("poison_marker", False) or str(target_doc.get("poison_payload", "") or "").strip()))

    return {
        "changed_title": int(changed_title),
        "changed_genres": int(changed_genres),
        "changed_synopsis": int(changed_synopsis),
        "changed_any_non_poison_fields": int(changed_any_non_poison_fields),
        "changed_only_poison_fields": int(changed_only_poison_fields),
        "sample_poisoned_movie_ids": sorted(poisoned_movie_ids)[:DIAGNOSTIC_SAMPLE_LIMIT],
        "modified_field_samples": modified_field_samples,
        "target_is_poisoned": bool(target_is_poisoned),
        "target_movie_id": int(target_movie_id) if target_movie_id is not None else None,
    }


def _normalize_genres(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        text = value.strip()
        if text == "":
            return []
        return [part.strip() for part in text.split("|") if part.strip()]
    return []
