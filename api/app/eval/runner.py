from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha256
import logging
from pathlib import Path
import random
import shutil
from typing import Any, Literal
from urllib.parse import urlparse

from api.app.data.paths import ES_BULK_MOVIES_JSONL, ES_BULK_POISONED_MOVIES_JSONL
from api.app.eval.metrics import (
    asr_at_k,
    hr_at_k,
    mean_metrics,
    metric_stats,
    metrics_delta,
    mrr_at_k,
    ndcg_at_k,
    paired_significance,
)
from api.app.llm.registry import LlmRegistry
from api.app.services.recs_service import (
    RecsService,
    load_defense_runtime_config,
    load_llm_config,
    recommendation_retrieval_size,
)
from api.app.services.users_service import UsersService
from api.app.services.indexing_service import get_index_provenance
from api.app.settings import Settings, get_es_client, get_settings
from common.schemas.attack_config import AttackConfig, load_attack_config
from common.schemas.defense_config import DefenseConfig
from common.schemas.llm_config import LlmConfig
from rag.recsys.candidate_gen import (
    build_es_query,
    build_retrieval_query,
    build_user_context,
    parse_hits,
)
from rag.recsys.ranker import rank_candidates

EvalMode = Literal["single", "batch", "full"]
BASE_METRIC_KEYS: tuple[str, ...] = ("hr", "ndcg", "mrr")
ASR_METRIC_KEY = "asr"
AUTO_TARGET_POOL_SIZE = 20
AUTO_TARGET_PICK_SEED = 42
AUTO_VIABLE_USER_SCAN_LIMIT = 200

logger = logging.getLogger(__name__)


def run_experiments(
    *,
    mode: EvalMode,
    label: str | None = None,
    k: int = 10,
    user_id: int | None = None,
    batch_size: int = 100,
    settings: Settings | None = None,
    es_client: Any | None = None,
    results_root: Path | None = None,
    allow_overwrite: bool = False,
    attack_config_path: Path | None = None,
    repeat_count: int = 1,
    seed: int = 42,
) -> dict[str, Any]:
    if k <= 0:
        raise ValueError("k must be >= 1")
    if batch_size <= 0:
        raise ValueError("batch_size must be >= 1")
    if repeat_count <= 0:
        raise ValueError("repeat_count must be >= 1")
    if seed < 0:
        raise ValueError("seed must be >= 0")

    logger.info(
        "eval_run_start mode=%s label=%s k=%s user_id=%s batch_size=%s repeat_count=%s seed=%s",
        mode,
        label,
        k,
        user_id,
        batch_size,
        repeat_count,
        seed,
    )

    if repeat_count > 1:
        return _run_repeated_experiments(
            mode=mode,
            label=label,
            k=k,
            user_id=user_id,
            batch_size=batch_size,
            settings=settings,
            es_client=es_client,
            results_root=results_root,
            allow_overwrite=allow_overwrite,
            attack_config_path=attack_config_path,
            repeat_count=repeat_count,
            seed=seed,
        )

    resolved_settings = settings or get_settings()
    resolved_es_client = es_client if es_client is not None else get_es_client()
    llm_registry = LlmRegistry(settings=resolved_settings)

    users_service = UsersService(settings=resolved_settings)
    recs_service = RecsService(settings=resolved_settings, es_client=resolved_es_client, llm_registry=llm_registry)

    relevant_by_user = _build_relevant_movies_map(users_service)
    llm_config = load_llm_config(settings=resolved_settings)
    _validate_eval_victim_llm_config(
        llm_config=llm_config,
        settings=resolved_settings,
        llm_registry=llm_registry,
    )

    resolved_attack_config_path = (
        attack_config_path.resolve()
        if attack_config_path is not None
        else resolved_settings.resolved_attack_config_path
    )
    attack_config = load_attack_config(resolved_attack_config_path)
    attack_config_sha256 = _hash_file(resolved_attack_config_path) if resolved_attack_config_path.exists() else None
    defense_config = load_defense_runtime_config(settings=resolved_settings)
    defense_config_path = resolved_settings.resolved_defense_config_path
    defense_config_sha256 = _hash_file(defense_config_path) if defense_config_path.exists() and defense_config_path.stat().st_size > 0 else None
    target_movie_id, eval_warnings, target_movie_source = _resolve_target_movie_id(
        attack_config=attack_config,
        users_service=users_service,
    )
    selected_user_ids = _resolve_user_ids(
        users_service=users_service,
        mode=mode,
        user_id=user_id,
        batch_size=batch_size,
        repeat_count=repeat_count,
        seed=seed,
    )
    if mode == "single":
        resolved_user_id, target_movie_id, target_movie_source, single_case_warnings = _resolve_single_eval_case(
            users_service=users_service,
            recs_service=recs_service,
            es_client=resolved_es_client,
            relevant_by_user=relevant_by_user,
            llm_config=llm_config,
            attack_config=attack_config,
            requested_user_id=user_id,
            target_movie_id=target_movie_id,
            target_movie_source=target_movie_source,
            k=k,
        )
        selected_user_ids = [resolved_user_id]
        eval_warnings.extend(single_case_warnings)

    attack_config_diagnostics, config_warnings = _build_attack_config_diagnostics(
        attack_config=attack_config,
        users_service=users_service,
        selected_user_ids=selected_user_ids,
        target_movie_id=target_movie_id,
    )
    eval_warnings.extend(config_warnings)
    eval_warnings.extend(
        _validate_poisoned_index_state(
            es_client=resolved_es_client,
            attack_config=attack_config,
            target_movie_id=target_movie_id,
        )
    )
    index_provenance, provenance_warnings = _resolve_eval_index_provenance(
        es_client=resolved_es_client,
        runtime_attack_config_sha256=attack_config_sha256,
        processed_dir=resolved_settings.resolved_processed_dir,
    )
    eval_warnings.extend(provenance_warnings)
    asr_applicable = _is_asr_applicable(
        attack_type=attack_config.attack_type,
        target_movie_id=target_movie_id,
    )
    asr_applicable_reason = _asr_applicability_reason(
        attack_type=attack_config.attack_type,
        target_movie_id=target_movie_id,
    )
    metric_keys: tuple[str, ...] = BASE_METRIC_KEYS + ((ASR_METRIC_KEY,) if asr_applicable else tuple())
    if not asr_applicable and target_movie_id is not None:
        eval_warnings.append(
            f"target_movie_id={target_movie_id} configured but ASR disabled for attack_type={attack_config.attack_type}"
        )

    logger.info(
        "eval_context_resolved mode=%s selected_users=%s attack_type=%s target_movie_id=%s target_source=%s asr_applicable=%s attack_config_diagnostics=%s",
        mode,
        len(selected_user_ids),
        attack_config.attack_type,
        target_movie_id,
        target_movie_source,
        asr_applicable,
        json.dumps(attack_config_diagnostics, sort_keys=True),
    )

    run_label = _normalize_label(label) if label is not None else _default_run_label()
    run_dir = resolve_run_dir(settings=resolved_settings, label=run_label, results_root=results_root)
    _prepare_run_dir(run_dir=run_dir, allow_overwrite=allow_overwrite)
    runtime_snapshot_paths = _write_runtime_config_snapshots(
        run_dir=run_dir,
        llm_config=llm_config,
        attack_config=attack_config,
        attack_config_sha256=attack_config_sha256,
        defense_config=defense_config,
        defense_config_sha256=defense_config_sha256,
    )

    per_user_rows: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    attack_trace_payload: dict[str, Any] | None = None
    attack_trace_path: Path | None = None

    for current_user_id in selected_user_ids:
        relevant = relevant_by_user.get(current_user_id, set())
        if not relevant:
            skipped.append({"user_id": current_user_id, "reason": "no_test_items"})
            continue

        try:
            baseline_result = recs_service.recommend_with_debug(
                user_id=current_user_id,
                mode="baseline",
                k=k,
                seen_history_split="train",
                strict_retrieval=True,
            )
            attacked_result = recs_service.recommend_with_debug(
                user_id=current_user_id,
                mode="attacked",
                k=k,
                seen_history_split="train",
                strict_retrieval=True,
            )
            defended_result = (
                recs_service.recommend_with_debug(
                    user_id=current_user_id,
                    mode="attacked",
                    k=k,
                    seen_history_split="train",
                    strict_retrieval=True,
                    defense_config_override=defense_config,
                )
                if defense_config.enabled
                else None
            )
            baseline = baseline_result["items"]
            attacked = attacked_result["items"]
            defended = defended_result["items"] if defended_result is not None else None
        except Exception as exc:  # noqa: BLE001
            skipped.append({"user_id": current_user_id, "reason": f"recommendation_error: {exc}"})
            continue

        baseline_ids = _extract_movie_ids(baseline)
        attacked_ids = _extract_movie_ids(attacked)
        defended_ids = _extract_movie_ids(defended or [])
        baseline_debug = baseline_result.get("debug")
        attacked_debug = attacked_result.get("debug")
        defended_debug = defended_result.get("debug") if defended_result is not None else None
        baseline_retrieval_ids = _extract_debug_movie_ids(baseline_debug, key="retrieved_from_es_movie_ids")
        attacked_retrieval_ids = _extract_debug_movie_ids(attacked_debug, key="retrieved_from_es_movie_ids")
        defended_retrieval_ids = _extract_debug_movie_ids(defended_debug, key="retrieved_from_es_movie_ids")

        baseline_hits = _relevant_hits_at_k(recommended=baseline_ids, relevant=relevant, k=k)
        attacked_hits = _relevant_hits_at_k(recommended=attacked_ids, relevant=relevant, k=k)

        baseline_metrics = {
            "hr": hr_at_k(baseline_ids, relevant, k),
            "ndcg": ndcg_at_k(baseline_ids, relevant, k),
            "mrr": mrr_at_k(baseline_ids, relevant, k),
        }
        attacked_metrics = {
            "hr": hr_at_k(attacked_ids, relevant, k),
            "ndcg": ndcg_at_k(attacked_ids, relevant, k),
            "mrr": mrr_at_k(attacked_ids, relevant, k),
        }
        defended_metrics = (
            {
                "hr": hr_at_k(defended_ids, relevant, k),
                "ndcg": ndcg_at_k(defended_ids, relevant, k),
                "mrr": mrr_at_k(defended_ids, relevant, k),
            }
            if defended is not None
            else None
        )
        if asr_applicable:
            baseline_metrics[ASR_METRIC_KEY] = asr_at_k(baseline_ids, target_movie_id, k)
            attacked_metrics[ASR_METRIC_KEY] = asr_at_k(attacked_ids, target_movie_id, k)
            if defended_metrics is not None:
                defended_metrics[ASR_METRIC_KEY] = asr_at_k(defended_ids, target_movie_id, k)

        overlap = _candidate_overlap_at_k(baseline_ids=baseline_ids, attacked_ids=attacked_ids, k=k)
        target_rank_baseline = _rank_of_target(recommended=baseline_ids, target_movie_id=target_movie_id, k=k)
        target_rank_attacked = _rank_of_target(recommended=attacked_ids, target_movie_id=target_movie_id, k=k)
        target_rank_lift = _target_rank_lift(
            baseline_rank=target_rank_baseline,
            attacked_rank=target_rank_attacked,
        )
        target_retrieval_rank_baseline = _rank_of_target(
            recommended=baseline_retrieval_ids,
            target_movie_id=target_movie_id,
            k=len(baseline_retrieval_ids),
        )
        target_retrieval_rank_attacked = _rank_of_target(
            recommended=attacked_retrieval_ids,
            target_movie_id=target_movie_id,
            k=len(attacked_retrieval_ids),
        )
        target_retrieval_rank_defended = _rank_of_target(
            recommended=defended_retrieval_ids,
            target_movie_id=target_movie_id,
            k=len(defended_retrieval_ids),
        )
        target_retrieval_rank_lift = _target_rank_lift(
            baseline_rank=target_retrieval_rank_baseline,
            attacked_rank=target_retrieval_rank_attacked,
        )
        defense_target_retrieval_rank_lift = _target_rank_lift(
            baseline_rank=target_retrieval_rank_attacked,
            attacked_rank=target_retrieval_rank_defended,
        )

        row = {
                "user_id": current_user_id,
                "relevant_test_count": len(relevant),
                "baseline_relevant_hits_at_k": baseline_hits,
                "attacked_relevant_hits_at_k": attacked_hits,
                "candidate_overlap_at_k": round(overlap, 6),
                "target_rank_baseline": target_rank_baseline,
                "target_rank_attacked": target_rank_attacked,
                "target_rank_lift": target_rank_lift,
                "target_in_retrieval_baseline": bool(target_retrieval_rank_baseline is not None),
                "target_in_retrieval_attacked": bool(target_retrieval_rank_attacked is not None),
                "target_retrieval_rank_baseline": target_retrieval_rank_baseline,
                "target_retrieval_rank_attacked": target_retrieval_rank_attacked,
                "target_retrieval_rank_lift": target_retrieval_rank_lift,
                "baseline": _round_metrics(baseline_metrics),
                "attacked": _round_metrics(attacked_metrics),
                "delta": _round_metrics(metrics_delta(baseline=baseline_metrics, attacked=attacked_metrics)),
            }
        if defended_metrics is not None:
            row["defended"] = _round_metrics(defended_metrics)
            row["defense_delta"] = _round_metrics(metrics_delta(baseline=attacked_metrics, attacked=defended_metrics))
            row["target_in_retrieval_defended"] = bool(target_retrieval_rank_defended is not None)
            row["target_retrieval_rank_defended"] = target_retrieval_rank_defended
            row["target_retrieval_defense_lift"] = defense_target_retrieval_rank_lift
        per_user_rows.append(row)

        logger.info(
            "eval_user_result user_id=%s mode=%s attack_type=%s relevant_test_count=%s baseline_hits_at_k=%s attacked_hits_at_k=%s overlap_at_k=%.6f target_rank_baseline=%s target_rank_attacked=%s target_retrieval_rank_baseline=%s target_retrieval_rank_attacked=%s",
            current_user_id,
            mode,
            attack_config.attack_type,
            len(relevant),
            baseline_hits,
            attacked_hits,
            overlap,
            target_rank_baseline,
            target_rank_attacked,
            target_retrieval_rank_baseline,
            target_retrieval_rank_attacked,
        )

        if baseline_hits == 0 and attacked_hits == 0:
            logger.warning(
                "eval_user_zero_hit_floor user_id=%s k=%s attack_type=%s target_movie_id=%s",
                current_user_id,
                k,
                attack_config.attack_type,
                target_movie_id,
            )

        if mode == "single":
            attack_trace_payload = {
                "mode": mode,
                "user_id": int(current_user_id),
                "k": int(k),
                "attack_config": attack_config.model_dump(),
                "attack_config_diagnostics": attack_config_diagnostics,
                "target_movie_id": int(target_movie_id) if target_movie_id is not None else None,
                "target_movie_source": target_movie_source,
                "asr_applicable": asr_applicable,
                "baseline_index": "movies",
                "attacked_index": "movies_poisoned",
                "relevant_test_movie_ids": sorted(int(item) for item in relevant),
                "baseline_debug": baseline_debug,
                "attacked_debug": attacked_debug,
                "defended_debug": defended_debug,
                "metrics_input": {
                    "baseline_ids": baseline_ids,
                    "attacked_ids": attacked_ids,
                    "defended_ids": defended_ids,
                    "baseline_retrieval_ids": baseline_retrieval_ids,
                    "attacked_retrieval_ids": attacked_retrieval_ids,
                    "defended_retrieval_ids": defended_retrieval_ids,
                    "baseline_metrics": _round_metrics(baseline_metrics),
                    "attacked_metrics": _round_metrics(attacked_metrics),
                    "delta_metrics": _round_metrics(metrics_delta(baseline=baseline_metrics, attacked=attacked_metrics)),
                    "defended_metrics": _round_metrics(defended_metrics) if defended_metrics is not None else None,
                    "defense_delta_metrics": _round_metrics(metrics_delta(baseline=attacked_metrics, attacked=defended_metrics))
                    if defended_metrics is not None
                    else None,
                    "candidate_overlap_at_k": round(overlap, 6),
                    "baseline_relevant_hits_at_k": baseline_hits,
                    "attacked_relevant_hits_at_k": attacked_hits,
                    "target_rank_baseline": target_rank_baseline,
                    "target_rank_attacked": target_rank_attacked,
                    "target_rank_lift": target_rank_lift,
                    "target_retrieval_rank_baseline": target_retrieval_rank_baseline,
                    "target_retrieval_rank_attacked": target_retrieval_rank_attacked,
                    "target_retrieval_rank_lift": target_retrieval_rank_lift,
                    "target_retrieval_rank_defended": target_retrieval_rank_defended,
                    "target_retrieval_defense_lift": defense_target_retrieval_rank_lift,
                },
            }

    if not per_user_rows:
        reason_text = _summarize_skip_reasons(skipped)
        raise RuntimeError(
            "No users were evaluated. Ensure processed files exist and selected users have test split rows. "
            f"Observed skip reasons: {reason_text}"
        )

    baseline_aggregate = _round_metrics(
        mean_metrics([row["baseline"] for row in per_user_rows], metric_keys)
    )
    attacked_aggregate = _round_metrics(
        mean_metrics([row["attacked"] for row in per_user_rows], metric_keys)
    )
    delta_aggregate = _round_metrics(metrics_delta(baseline=baseline_aggregate, attacked=attacked_aggregate))
    target_retrieval_aggregate = _aggregate_target_retrieval(per_user_rows=per_user_rows, target_movie_id=target_movie_id)
    defended_aggregate = (
        _round_metrics(mean_metrics([row["defended"] for row in per_user_rows if isinstance(row.get("defended"), dict)], metric_keys))
        if defense_config.enabled and any(isinstance(row.get("defended"), dict) for row in per_user_rows)
        else None
    )
    defense_delta_aggregate = (
        _round_metrics(metrics_delta(baseline=attacked_aggregate, attacked=defended_aggregate))
        if isinstance(defended_aggregate, dict)
        else None
    )

    metrics_path = run_dir / "metrics.json"
    if attack_trace_payload is not None:
        attack_trace_path = run_dir / "attack_trace.json"
        attack_trace_path.write_text(json.dumps(attack_trace_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    payload: dict[str, Any] = {
        "label": run_label,
        "mode": mode,
        "k": int(k),
        "requested_users": len(selected_user_ids),
        "evaluated_users": len(per_user_rows),
        "skipped_users": len(skipped),
        "metadata": {
            "attack_type": attack_config.attack_type,
            "target_movie_id": int(target_movie_id) if target_movie_id is not None else None,
            "target_movie_source": target_movie_source,
            "asr_applicable": asr_applicable,
            "asr_applicable_reason": asr_applicable_reason,
            "attack_config_diagnostics": attack_config_diagnostics,
            "attack_config_sha256": attack_config_sha256,
            "attack_config_path": str(resolved_attack_config_path),
            "defense_enabled": defense_config.enabled,
            "defense_config": defense_config.model_dump(),
            "defense_config_sha256": defense_config_sha256,
            "defense_config_path": str(defense_config_path),
            "index_provenance": index_provenance,
            "runtime_snapshot_paths": runtime_snapshot_paths,
            "metric_keys": list(metric_keys),
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "repeat_count": repeat_count,
            "seed": seed,
        },
        "baseline": baseline_aggregate,
        "attacked": attacked_aggregate,
        "delta": delta_aggregate,
        "target_retrieval": target_retrieval_aggregate,
        "per_user": per_user_rows,
        "skipped": skipped,
    }
    if defended_aggregate is not None:
        payload["defended"] = defended_aggregate
        payload["defense_delta"] = defense_delta_aggregate
    if eval_warnings:
        payload["warnings"] = list(eval_warnings)
    if attack_trace_path is not None:
        payload["attack_trace_path"] = str(attack_trace_path)

    metrics_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_path = run_dir / "experiment_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "label": run_label,
                "mode": mode,
                "k": int(k),
                "requested_users": len(selected_user_ids),
                "evaluated_users": len(per_user_rows),
                "skipped_users": len(skipped),
                "attack_config_sha256": attack_config_sha256,
                "attack_config_path": str(resolved_attack_config_path),
                "defense_config_sha256": defense_config_sha256,
                "defense_config_path": str(defense_config_path),
                "index_provenance": index_provenance,
                "runtime_snapshot_paths": runtime_snapshot_paths,
                "metrics_path": str(metrics_path),
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "repeat_count": repeat_count,
                "seed": seed,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    summary = {
        "label": run_label,
        "run_dir": str(run_dir),
        "metrics_path": str(metrics_path),
        "mode": mode,
        "k": int(k),
        "requested_users": len(selected_user_ids),
        "evaluated_users": len(per_user_rows),
        "skipped_users": len(skipped),
        "baseline": baseline_aggregate,
        "attacked": attacked_aggregate,
        "delta": delta_aggregate,
        "target_retrieval": target_retrieval_aggregate,
        "target_movie_id": int(target_movie_id) if target_movie_id is not None else None,
        "target_movie_source": target_movie_source,
        "asr_applicable": asr_applicable,
        "attack_config_diagnostics": attack_config_diagnostics,
        "attack_config_sha256": attack_config_sha256,
        "attack_config_path": str(resolved_attack_config_path),
        "defense_config_sha256": defense_config_sha256,
        "defense_config_path": str(defense_config_path),
        "defense_enabled": defense_config.enabled,
        "index_provenance": index_provenance,
        "runtime_snapshot_paths": runtime_snapshot_paths,
        "manifest_path": str(manifest_path),
        "metric_keys": list(metric_keys),
        "repeat_count": repeat_count,
        "seed": seed,
    }
    if defended_aggregate is not None:
        summary["defended"] = defended_aggregate
        summary["defense_delta"] = defense_delta_aggregate
    if eval_warnings:
        summary["warnings"] = list(eval_warnings)
    if attack_trace_path is not None:
        summary["attack_trace_path"] = str(attack_trace_path)
    logger.info(
        "eval_run_complete label=%s mode=%s attack_type=%s evaluated_users=%s baseline=%s attacked=%s delta=%s target_retrieval=%s metrics_path=%s",
        run_label,
        mode,
        attack_config.attack_type,
        len(per_user_rows),
        baseline_aggregate,
        attacked_aggregate,
        delta_aggregate,
        target_retrieval_aggregate,
        metrics_path,
    )
    return summary


def _run_repeated_experiments(
    *,
    mode: EvalMode,
    label: str | None,
    k: int,
    user_id: int | None,
    batch_size: int,
    settings: Settings | None,
    es_client: Any | None,
    results_root: Path | None,
    allow_overwrite: bool,
    attack_config_path: Path | None,
    repeat_count: int,
    seed: int,
) -> dict[str, Any]:
    resolved_settings = settings or get_settings()
    resolved_es_client = es_client if es_client is not None else get_es_client()
    run_label = _normalize_label(label) if label is not None else _default_run_label()
    run_dir = resolve_run_dir(settings=resolved_settings, label=run_label, results_root=results_root)
    _prepare_run_dir(run_dir=run_dir, allow_overwrite=allow_overwrite)

    llm_config = load_llm_config(settings=resolved_settings)
    resolved_attack_config_path = (
        attack_config_path.resolve()
        if attack_config_path is not None
        else resolved_settings.resolved_attack_config_path
    )
    attack_config = load_attack_config(resolved_attack_config_path)
    attack_config_sha256 = _hash_file(resolved_attack_config_path) if resolved_attack_config_path.exists() else None
    defense_config = load_defense_runtime_config(settings=resolved_settings)
    defense_config_path = resolved_settings.resolved_defense_config_path
    defense_config_sha256 = _hash_file(defense_config_path) if defense_config_path.exists() and defense_config_path.stat().st_size > 0 else None
    runtime_snapshot_paths = _write_runtime_config_snapshots(
        run_dir=run_dir,
        llm_config=llm_config,
        attack_config=attack_config,
        attack_config_sha256=attack_config_sha256,
        defense_config=defense_config,
        defense_config_sha256=defense_config_sha256,
    )

    repeat_root = run_dir / "repeats"
    repeat_root.mkdir(parents=True, exist_ok=True)

    repeat_summaries: list[dict[str, Any]] = []
    repeat_payloads: list[dict[str, Any]] = []
    for repeat_index in range(repeat_count):
        repeat_label = f"repeat_{repeat_index + 1:03d}"
        repeat_summary = run_experiments(
            mode=mode,
            label=repeat_label,
            k=k,
            user_id=user_id,
            batch_size=batch_size,
            settings=resolved_settings,
            es_client=resolved_es_client,
            results_root=repeat_root,
            allow_overwrite=True,
            attack_config_path=resolved_attack_config_path,
            repeat_count=1,
            seed=seed + repeat_index,
        )
        repeat_summaries.append(repeat_summary)
        repeat_payloads.append(_load_metrics_payload(Path(str(repeat_summary["metrics_path"]))))

    baseline = _mean_metric_sections(repeat_payloads, "baseline")
    attacked = _mean_metric_sections(repeat_payloads, "attacked")
    delta = _mean_metric_sections(repeat_payloads, "delta")
    defended = _mean_metric_sections(repeat_payloads, "defended")
    defense_delta = _mean_metric_sections(repeat_payloads, "defense_delta")
    warnings = _merge_repeat_warnings(repeat_payloads)
    target_retrieval = _aggregate_repeat_target_retrieval(repeat_payloads)
    repeat_stats = _build_repeat_stats(repeat_payloads)
    first_payload = repeat_payloads[0] if repeat_payloads else {}
    first_metadata = first_payload.get("metadata") if isinstance(first_payload.get("metadata"), dict) else {}

    payload: dict[str, Any] = {
        "label": run_label,
        "mode": mode,
        "k": int(k),
        "requested_users": int(first_payload.get("requested_users", batch_size if mode == "batch" else 0)),
        "evaluated_users": int(first_payload.get("evaluated_users", 0)),
        "skipped_users": int(first_payload.get("skipped_users", 0)),
        "metadata": {
            **first_metadata,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "repeat_count": repeat_count,
            "seed": seed,
            "runtime_snapshot_paths": runtime_snapshot_paths,
            "repeat_run_dirs": [str(summary["run_dir"]) for summary in repeat_summaries],
        },
        "baseline": baseline,
        "attacked": attacked,
        "delta": delta,
        "target_retrieval": target_retrieval,
        "per_user": [],
        "skipped": [],
        "repeat_stats": repeat_stats,
        "repeat_runs": repeat_summaries,
    }
    if defended:
        payload["defended"] = defended
    if defense_delta:
        payload["defense_delta"] = defense_delta
    if warnings:
        payload["warnings"] = warnings

    metrics_path = run_dir / "metrics.json"
    metrics_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_path = run_dir / "experiment_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "label": run_label,
                "mode": mode,
                "k": int(k),
                "requested_users": payload["requested_users"],
                "evaluated_users": payload["evaluated_users"],
                "skipped_users": payload["skipped_users"],
                "attack_config_sha256": attack_config_sha256,
                "attack_config_path": str(resolved_attack_config_path),
                "defense_config_sha256": defense_config_sha256,
                "defense_config_path": str(defense_config_path),
                "runtime_snapshot_paths": runtime_snapshot_paths,
                "metrics_path": str(metrics_path),
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "repeat_count": repeat_count,
                "seed": seed,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    summary: dict[str, Any] = {
        "label": run_label,
        "run_dir": str(run_dir),
        "metrics_path": str(metrics_path),
        "manifest_path": str(manifest_path),
        "mode": mode,
        "k": int(k),
        "requested_users": payload["requested_users"],
        "evaluated_users": payload["evaluated_users"],
        "skipped_users": payload["skipped_users"],
        "baseline": baseline,
        "attacked": attacked,
        "delta": delta,
        "target_retrieval": target_retrieval,
        "repeat_count": repeat_count,
        "seed": seed,
        "runtime_snapshot_paths": runtime_snapshot_paths,
        "repeat_stats": repeat_stats,
    }
    if defended:
        summary["defended"] = defended
    if defense_delta:
        summary["defense_delta"] = defense_delta
    if warnings:
        summary["warnings"] = warnings
    return summary


def resolve_run_dir(*, settings: Settings, label: str, results_root: Path | None = None) -> Path:
    base = results_root.resolve() if results_root is not None else (settings.resolved_data_root / "results" / "runs")
    return (base / label).resolve()


def _prepare_run_dir(*, run_dir: Path, allow_overwrite: bool) -> None:
    if run_dir.exists() and any(run_dir.iterdir()):
        if not allow_overwrite:
            raise RuntimeError(
                f"Run label '{run_dir.name}' already exists at {run_dir}. "
                "Use a different label or pass overwrite=true to replace artifacts."
            )
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)


def _hash_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _load_metrics_payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _mean_metric_sections(repeat_payloads: list[dict[str, Any]], key: str) -> dict[str, float]:
    rows = [item.get(key) for item in repeat_payloads if isinstance(item.get(key), dict)]
    if not rows:
        return {}
    metric_keys = sorted({metric_key for row in rows for metric_key in row.keys()})
    return _round_metrics(mean_metrics(rows, metric_keys))


def _merge_repeat_warnings(repeat_payloads: list[dict[str, Any]]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for payload in repeat_payloads:
        warnings = payload.get("warnings", [])
        if not isinstance(warnings, list):
            continue
        for item in warnings:
            text = str(item).strip()
            if text == "" or text in seen:
                continue
            seen.add(text)
            output.append(text)
    return output


def _aggregate_repeat_target_retrieval(repeat_payloads: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [payload.get("target_retrieval") for payload in repeat_payloads if isinstance(payload.get("target_retrieval"), dict)]
    if not rows:
        return {}

    output = dict(rows[0])
    numeric_keys = [
        key
        for key in output.keys()
        if key.endswith("_rate") or key.startswith("target_retrieval_mean_rank")
    ]
    for key in numeric_keys:
        values = [float(row[key]) for row in rows if isinstance(row.get(key), (int, float))]
        if values:
            output[key] = round(sum(values) / float(len(values)), 6)
    count_keys = [
        "users",
        "target_in_retrieval_baseline_users",
        "target_in_retrieval_attacked_users",
        "target_in_retrieval_defended_users",
        "target_retrieval_rank_changed_users",
        "target_retrieval_defense_rank_changed_users",
    ]
    for key in count_keys:
        values = [int(row[key]) for row in rows if isinstance(row.get(key), int)]
        if values:
            output[key] = int(round(sum(values) / float(len(values))))
    return output


def _build_repeat_stats(repeat_payloads: list[dict[str, Any]]) -> dict[str, Any]:
    def _section(section_key: str) -> dict[str, Any] | None:
        rows = [payload.get(section_key) for payload in repeat_payloads if isinstance(payload.get(section_key), dict)]
        if not rows:
            return None
        metric_keys = sorted({metric_key for row in rows for metric_key in row.keys()})
        return {
            "metrics": {
                key: _round_stats(metric_stats([float(row.get(key, 0.0)) for row in rows]))
                for key in metric_keys
            },
            "significance": {
                key: _round_stats(paired_significance([float(row.get(key, 0.0)) for row in rows]))
                for key in metric_keys
            }
            if section_key in {"delta", "defense_delta"}
            else {},
        }

    return {
        "repeat_count": len(repeat_payloads),
        "seed": int(
            (
                repeat_payloads[0].get("metadata", {}).get("seed")
                if repeat_payloads and isinstance(repeat_payloads[0].get("metadata"), dict)
                else 42
            )
            or 42
        ),
        "baseline": _section("baseline"),
        "attacked": _section("attacked"),
        "delta": _section("delta"),
        "defended": _section("defended"),
        "defense_delta": _section("defense_delta"),
    }


def _round_stats(values: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in values.items():
        if isinstance(value, float):
            output[key] = round(value, 6)
        else:
            output[key] = value
    return output


def _write_runtime_config_snapshots(
    *,
    run_dir: Path,
    llm_config: LlmConfig,
    attack_config: AttackConfig,
    attack_config_sha256: str | None,
    defense_config: DefenseConfig,
    defense_config_sha256: str | None,
) -> dict[str, str]:
    llm_path = run_dir / "llm_config.runtime.json"
    attack_path = run_dir / "attack_config.runtime.json"
    defense_path = run_dir / "defense_config.runtime.json"
    llm_path.write_text(json.dumps(llm_config.model_dump(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    attack_payload = attack_config.model_dump()
    if attack_config_sha256 is not None:
        attack_payload["sha256"] = attack_config_sha256
    attack_path.write_text(json.dumps(attack_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    defense_payload = defense_config.model_dump()
    if defense_config_sha256 is not None:
        defense_payload["sha256"] = defense_config_sha256
    defense_path.write_text(json.dumps(defense_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "llm_config_runtime_path": str(llm_path),
        "attack_config_runtime_path": str(attack_path),
        "defense_config_runtime_path": str(defense_path),
    }


def _resolve_eval_index_provenance(
    *,
    es_client: Any,
    runtime_attack_config_sha256: str | None,
    processed_dir: Path,
) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    output: dict[str, Any] = {}
    for logical_index in ("movies", "movies_poisoned"):
        try:
            resolved = get_index_provenance(es_client=es_client, logical_index_name=logical_index)
        except Exception as exc:  # noqa: BLE001
            warnings.append(
                f"index_provenance_lookup_failed index={logical_index} error={type(exc).__name__}: {exc}"
            )
            continue
        if resolved is None:
            warnings.append(f"index_provenance_unavailable index={logical_index}")
            continue
        output[logical_index] = resolved

    attacked = output.get("movies_poisoned")
    if isinstance(attacked, dict) and runtime_attack_config_sha256 is not None:
        provenance = attacked.get("provenance")
        if isinstance(provenance, dict):
            indexed_attack_sha = provenance.get("attack_config_sha256")
            if not isinstance(indexed_attack_sha, str) or indexed_attack_sha.strip() == "":
                raise RuntimeError(
                    "Attack provenance missing for movies_poisoned index. "
                    "Reindex poisoned data via canonical indexing path before eval."
                )
            if indexed_attack_sha != runtime_attack_config_sha256:
                raise RuntimeError(
                    "Attack config/index provenance mismatch: runtime attack_config.json differs from "
                    f"movies_poisoned indexed provenance (runtime={runtime_attack_config_sha256}, indexed={indexed_attack_sha}). "
                    "Rebuild poisoned bulk and reindex before eval."
                )

    for logical_index, bulk_name in (
        ("movies", ES_BULK_MOVIES_JSONL),
        ("movies_poisoned", ES_BULK_POISONED_MOVIES_JSONL),
    ):
        resolved = output.get(logical_index)
        if not isinstance(resolved, dict):
            continue
        provenance = resolved.get("provenance")
        if not isinstance(provenance, dict):
            continue
        indexed_bulk_sha = provenance.get("bulk_sha256")
        if not isinstance(indexed_bulk_sha, str) or indexed_bulk_sha.strip() == "":
            warnings.append(f"index_provenance_missing_bulk_sha index={logical_index}")
            continue

        bulk_path = (processed_dir / bulk_name).resolve()
        if not bulk_path.exists() or bulk_path.stat().st_size == 0:
            warnings.append(
                f"processed_bulk_unavailable_for_provenance_check index={logical_index} path={bulk_path}"
            )
            continue

        runtime_bulk_sha = _hash_file(bulk_path)
        if runtime_bulk_sha != indexed_bulk_sha:
            raise RuntimeError(
                f"Processed data/index provenance mismatch for {logical_index}: "
                f"processed bulk sha256 ({runtime_bulk_sha}) differs from indexed provenance ({indexed_bulk_sha}). "
                "Reindex before running eval."
            )
    return output, warnings


def _resolve_user_ids(
    *,
    users_service: UsersService,
    mode: EvalMode,
    user_id: int | None,
    batch_size: int,
    repeat_count: int,
    seed: int,
) -> list[int]:
    all_users = users_service.list_users(limit=1_000_000)
    ordered_ids = sorted(int(item["user_id"]) for item in all_users)

    if mode == "single":
        if user_id is None:
            return []
        if int(user_id) not in set(ordered_ids):
            raise ValueError(f"Unknown user_id: {user_id}")
        return [int(user_id)]

    if mode == "batch":
        if batch_size >= len(ordered_ids):
            return ordered_ids
        if repeat_count == 1:
            return ordered_ids[:batch_size]
        return sorted(random.Random(seed).sample(ordered_ids, batch_size))

    return ordered_ids


def _build_relevant_movies_map(users_service: UsersService) -> dict[int, set[int]]:
    splits = users_service.splits_df.copy()
    if splits.empty:
        return {}

    splits["user_id"] = splits["user_id"].astype("int64")
    splits["movie_id"] = splits["movie_id"].astype("int64")
    splits["split"] = splits["split"].astype(str)

    filtered = splits[splits["split"] == "test"]
    output: dict[int, set[int]] = {}
    for row in filtered.itertuples(index=False):
        output.setdefault(int(row.user_id), set()).add(int(row.movie_id))
    return output


def _extract_movie_ids(items: list[dict[str, Any]]) -> list[int]:
    output: list[int] = []
    for item in items:
        try:
            output.append(int(item["movie_id"]))
        except Exception:  # noqa: BLE001
            continue
    return output


def _extract_debug_movie_ids(debug_payload: object, *, key: str) -> list[int]:
    if not isinstance(debug_payload, dict):
        return []
    raw = debug_payload.get(key, [])
    if not isinstance(raw, list):
        return []
    output: list[int] = []
    for item in raw:
        try:
            output.append(int(item))
        except Exception:  # noqa: BLE001
            continue
    return output


def _is_targeted_attack_type(attack_type: str) -> bool:
    return attack_type in {"targeted_promotion", "prompt_injection"}


def _resolve_target_movie_id(
    *,
    attack_config: AttackConfig,
    users_service: UsersService,
) -> tuple[int | None, list[str], str]:
    configured_target = attack_config.target_movie_id
    if configured_target is not None:
        return int(configured_target), [], "configured"

    if attack_config.attack_type not in {"targeted_promotion", "prompt_injection"}:
        return None, [], "none"

    selected = _auto_pick_target_movie_id(users_service=users_service)
    warnings = [
        f"target_movie_id is not set for attack_type={attack_config.attack_type}; "
        f"auto-selected deterministic target_movie_id={selected} (seed={AUTO_TARGET_PICK_SEED}). "
        "Set data/config/attack_config.json:target_movie_id to avoid automatic selection."
    ]
    return selected, warnings, "auto_selected"


def _resolve_single_eval_case(
    *,
    users_service: UsersService,
    recs_service: RecsService,
    es_client: Any,
    relevant_by_user: dict[int, set[int]],
    llm_config: LlmConfig,
    attack_config: AttackConfig,
    requested_user_id: int | None,
    target_movie_id: int | None,
    target_movie_source: str,
    k: int,
) -> tuple[int, int | None, str, list[str]]:
    ordered_user_ids = sorted(int(item["user_id"]) for item in users_service.list_users(limit=1_000_000))
    if not ordered_user_ids:
        raise RuntimeError("No users found in processed dataset; run data prepare first.")

    if requested_user_id is not None:
        selected_user_id = int(requested_user_id)
        if selected_user_id not in set(ordered_user_ids):
            raise ValueError(f"Unknown user_id: {selected_user_id}")
        warnings = _manual_single_case_warnings(
            users_service=users_service,
            es_client=es_client,
            relevant_by_user=relevant_by_user,
            llm_config=llm_config,
            user_id=selected_user_id,
            target_movie_id=target_movie_id,
            k=k,
        )
        return selected_user_id, target_movie_id, target_movie_source, warnings

    if not _is_targeted_attack_type(attack_config.attack_type):
        selected_user_id = int(ordered_user_ids[0])
        return (
            selected_user_id,
            target_movie_id,
            target_movie_source,
            ["mode=single without user_id defaulted to first available user_id because attack is non-targeted."],
        )

    candidate = _auto_select_viable_single_case(
        users_service=users_service,
        es_client=es_client,
        relevant_by_user=relevant_by_user,
        llm_config=llm_config,
        target_movie_id=target_movie_id,
        k=k,
    )
    if candidate is None:
        raise RuntimeError(
            "Unable to auto-select a viable single-user targeted case. "
            "No user satisfied: baseline_relevant_hits_at_k>0, target not in train history, and target retrievable "
            "from attacked candidates. Provide --user-id manually or update attack_config target/movie setup."
        )

    resolved_source = "auto_viable_pair"
    warnings = [
        "Auto-selected viable single-user targeted case: "
        f"user_id={candidate['user_id']} target_movie_id={candidate['target_movie_id']} "
        f"(baseline_hits_preview={candidate['baseline_hits_preview']} "
        f"attacked_retrieval_rank={candidate['attacked_retrieval_rank']})."
    ]
    return int(candidate["user_id"]), int(candidate["target_movie_id"]), resolved_source, warnings


def _manual_single_case_warnings(
    *,
    users_service: UsersService,
    es_client: Any,
    relevant_by_user: dict[int, set[int]],
    llm_config: LlmConfig,
    user_id: int,
    target_movie_id: int | None,
    k: int,
) -> list[str]:
    if target_movie_id is None:
        return []
    try:
        diagnosis = _single_case_diagnosis(
            users_service=users_service,
            es_client=es_client,
            relevant_by_user=relevant_by_user,
            llm_config=llm_config,
            user_id=user_id,
            target_movie_id=target_movie_id,
            k=k,
        )
    except Exception as exc:  # noqa: BLE001
        return [
            "Manual single-user viability precheck skipped due to retrieval preview failure: "
            f"{type(exc).__name__}: {exc}"
        ]
    if diagnosis["viable"]:
        return []
    return [
        "Manual single-user pair appears low-viability for target attack: "
        f"user_id={user_id} target_movie_id={target_movie_id} reasons={diagnosis['reasons']}"
    ]


def _auto_select_viable_single_case(
    *,
    users_service: UsersService,
    es_client: Any,
    relevant_by_user: dict[int, set[int]],
    llm_config: LlmConfig,
    target_movie_id: int | None,
    k: int,
) -> dict[str, Any] | None:
    ordered_user_ids = sorted(int(item["user_id"]) for item in users_service.list_users(limit=1_000_000))
    viable_candidates: list[dict[str, Any]] = []

    for current_user_id in ordered_user_ids[:AUTO_VIABLE_USER_SCAN_LIMIT]:
        diagnosis = _single_case_diagnosis(
            users_service=users_service,
            es_client=es_client,
            relevant_by_user=relevant_by_user,
            llm_config=llm_config,
            user_id=current_user_id,
            target_movie_id=target_movie_id,
            k=k,
        )
        if not diagnosis["viable"]:
            continue
        viable_candidates.append(diagnosis)

    if not viable_candidates:
        return None

    viable_candidates.sort(
        key=lambda item: (
            int(item.get("attacked_retrieval_rank", 10_000)),
            -int(item.get("baseline_hits_preview", 0)),
            int(item.get("user_id", 10_000)),
        )
    )
    return viable_candidates[0]


def _single_case_diagnosis(
    *,
    users_service: UsersService,
    es_client: Any,
    relevant_by_user: dict[int, set[int]],
    llm_config: LlmConfig,
    user_id: int,
    target_movie_id: int | None,
    k: int,
) -> dict[str, Any]:
    relevant = relevant_by_user.get(user_id, set())
    if not relevant:
        return {
            "user_id": int(user_id),
            "target_movie_id": target_movie_id,
            "viable": False,
            "reasons": ["user_has_no_test_items"],
            "baseline_hits_preview": 0,
            "attacked_retrieval_rank": None,
        }

    profile = users_service.get_profile(user_id)
    if profile is None:
        return {
            "user_id": int(user_id),
            "target_movie_id": target_movie_id,
            "viable": False,
            "reasons": ["unknown_user_profile"],
            "baseline_hits_preview": 0,
            "attacked_retrieval_rank": None,
        }

    history_train = users_service.get_history(user_id, split="train")
    seen_movie_ids = {int(item["movie_id"]) for item in history_train}
    context = build_user_context(profile=profile, train_history=history_train)
    query_text = build_retrieval_query(context)
    query_body = build_es_query(query_text=query_text, seen_movie_ids=seen_movie_ids)
    retrieval_size = recommendation_retrieval_size(ranking_mode=llm_config.ranking_mode, k=k)

    baseline_candidates = _preview_retrieved_candidates(
        es_client=es_client,
        index_name="movies",
        query_body=query_body,
        size=retrieval_size,
        seen_movie_ids=seen_movie_ids,
    )
    attacked_candidates = _preview_retrieved_candidates(
        es_client=es_client,
        index_name="movies_poisoned",
        query_body=query_body,
        size=retrieval_size,
        seen_movie_ids=seen_movie_ids,
    )

    baseline_ranked = rank_candidates(candidates=baseline_candidates, user_top_genres=context.top_genres, k=k)
    baseline_ids = [item.candidate.movie_id for item in baseline_ranked]
    baseline_hits = _relevant_hits_at_k(recommended=baseline_ids, relevant=relevant, k=k)

    baseline_retrieval_ids = [item.movie_id for item in baseline_candidates]
    attacked_retrieval_ids = [item.movie_id for item in attacked_candidates]
    effective_target = target_movie_id
    if effective_target is None:
        for movie_id in attacked_retrieval_ids:
            if movie_id in seen_movie_ids:
                continue
            if movie_id in baseline_ids:
                continue
            effective_target = int(movie_id)
            break

    reasons: list[str] = []
    if baseline_hits <= 0:
        reasons.append("baseline_relevant_hits_preview_is_zero")
    if effective_target is None:
        reasons.append("no_candidate_target_found_in_attacked_retrieval")
    if effective_target is not None and effective_target in seen_movie_ids:
        reasons.append("target_in_user_train_history")

    attacked_retrieval_rank = _rank_of_target(
        recommended=attacked_retrieval_ids,
        target_movie_id=effective_target,
        k=len(attacked_retrieval_ids),
    )
    if effective_target is not None and attacked_retrieval_rank is None:
        reasons.append("target_missing_from_attacked_retrieval")

    viable = len(reasons) == 0
    return {
        "user_id": int(user_id),
        "target_movie_id": int(effective_target) if effective_target is not None else None,
        "viable": viable,
        "reasons": reasons,
        "baseline_hits_preview": int(baseline_hits),
        "attacked_retrieval_rank": attacked_retrieval_rank,
        "baseline_retrieval_size": len(baseline_retrieval_ids),
        "attacked_retrieval_size": len(attacked_retrieval_ids),
        "query_text": query_text,
    }


def _preview_retrieved_candidates(
    *,
    es_client: Any,
    index_name: str,
    query_body: dict[str, Any],
    size: int,
    seen_movie_ids: set[int],
) -> list[Any]:
    response = es_client.search(index=index_name, query=query_body, size=size)
    hits_raw = _response_get(response, "hits", {})
    hits = _response_get(hits_raw, "hits", [])
    if not isinstance(hits, list):
        return []
    return parse_hits(hits=hits, seen_movie_ids=seen_movie_ids)


def _build_attack_config_diagnostics(
    *,
    attack_config: AttackConfig,
    users_service: UsersService,
    selected_user_ids: list[int],
    target_movie_id: int | None,
) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    movie_ids: set[int] = set()
    if "movie_id" in users_service.movies_df.columns:
        for raw in users_service.movies_df["movie_id"].tolist():
            try:
                movie_ids.add(int(raw))
            except Exception:  # noqa: BLE001
                continue

    total_movies = len(movie_ids)
    expected_poison_docs = int(round(float(attack_config.poison_fraction) * float(total_movies)))
    target_exists_in_movies = None if target_movie_id is None else bool(target_movie_id in movie_ids)
    payload_text_nonempty = bool(attack_config.payload_text.strip())
    keyword_count = len(attack_config.keyword_list)
    retrieval_fields = {"title", "genres", "synopsis"}
    target_field_overlap = [field for field in attack_config.target_fields if field in retrieval_fields]

    selected_target_train_users: list[int] = []
    if target_movie_id is not None and not users_service.splits_df.empty:
        splits = users_service.splits_df.copy()
        if {"user_id", "movie_id", "split"}.issubset(splits.columns):
            splits["user_id"] = splits["user_id"].astype("int64")
            splits["movie_id"] = splits["movie_id"].astype("int64")
            splits["split"] = splits["split"].astype(str)
            target_train = splits[(splits["split"] == "train") & (splits["movie_id"] == int(target_movie_id))]
            selected_set = set(int(item) for item in selected_user_ids)
            selected_target_train_users = sorted(int(item) for item in set(target_train["user_id"].tolist()) if int(item) in selected_set)

    if expected_poison_docs <= 0:
        warnings.append(
            "attack_config_diagnostics: poison_fraction rounds to zero poisoned docs; increase poison_fraction or dataset size."
        )
    if _is_targeted_attack_type(attack_config.attack_type) and target_movie_id is not None and not target_exists_in_movies:
        warnings.append(
            f"attack_config_diagnostics: target_movie_id={target_movie_id} does not exist in processed movies dataset."
        )
    if _is_targeted_attack_type(attack_config.attack_type) and not payload_text_nonempty:
        warnings.append(
            "attack_config_diagnostics: payload_text is empty; poisoned payload context may not affect reranking prompts."
        )
    if _is_targeted_attack_type(attack_config.attack_type) and keyword_count == 0:
        warnings.append(
            "attack_config_diagnostics: keyword_list is empty; targeted retrieval boost is likely weak."
        )
    if selected_target_train_users:
        warnings.append(
            f"attack_config_diagnostics: target_movie_id={target_movie_id} exists in train history for selected users={selected_target_train_users}; "
            "target exposure conditions may be unrealistic for attack evaluation."
        )
    if attack_config.target_boost_policy != "disabled" and not target_field_overlap:
        warnings.append(
            "attack_config_diagnostics: target_fields has no retrieval-relevant overlap with {title,genres,synopsis}."
        )

    diagnostics: dict[str, Any] = {
        "attack_type": attack_config.attack_type,
        "poison_fraction": float(attack_config.poison_fraction),
        "total_movies": int(total_movies),
        "expected_poisoned_docs": int(expected_poison_docs),
        "target_movie_id": int(target_movie_id) if target_movie_id is not None else None,
        "target_exists_in_movies": target_exists_in_movies,
        "selected_user_ids": [int(item) for item in selected_user_ids],
        "target_in_selected_users_train": selected_target_train_users,
        "payload_text_nonempty": payload_text_nonempty,
        "keyword_count": int(keyword_count),
        "target_boost_policy": attack_config.target_boost_policy,
        "target_boost_strength": int(attack_config.target_boost_strength),
        "target_fields": list(attack_config.target_fields),
        "target_fields_retrieval_overlap": target_field_overlap,
    }
    return diagnostics, warnings


def _auto_pick_target_movie_id(*, users_service: UsersService) -> int:
    movies = users_service.movies_df.copy()
    if movies.empty or "movie_id" not in movies.columns:
        raise RuntimeError(
            "Unable to auto-select target_movie_id: processed movies.parquet is missing/empty or lacks movie_id. "
            "Run data prepare first."
        )

    ids: list[int] = []
    for raw in movies["movie_id"].tolist():
        try:
            ids.append(int(raw))
        except Exception:  # noqa: BLE001
            continue
    if not ids:
        raise RuntimeError(
            "Unable to auto-select target_movie_id: no valid movie IDs found in processed movies.parquet. "
            "Run data prepare first."
        )

    pool = sorted(set(ids))[:AUTO_TARGET_POOL_SIZE]
    return int(random.Random(AUTO_TARGET_PICK_SEED).choice(pool))


def _summarize_skip_reasons(skipped: list[dict[str, Any]], *, max_reasons: int = 3) -> str:
    if not skipped:
        return "none"
    counts: dict[str, int] = {}
    for item in skipped:
        reason = str(item.get("reason", "unknown")).strip() or "unknown"
        counts[reason] = counts.get(reason, 0) + 1
    ordered = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    top = ordered[:max_reasons]
    return "; ".join(f"{reason} (x{count})" for reason, count in top)


def _validate_poisoned_index_state(
    *,
    es_client: Any,
    attack_config: AttackConfig,
    target_movie_id: int | None,
) -> list[str]:
    warnings: list[str] = []
    if float(attack_config.poison_fraction) <= 0.0:
        return warnings
    if not hasattr(es_client, "count"):
        return [
            "Poisoned index validation skipped because es_client.count is unavailable; "
            "cannot confirm poison_marker coverage."
        ]

    try:
        response = es_client.count(index="movies_poisoned", query={"term": {"poison_marker": True}})
        poison_marked = int(response.get("count", 0)) if hasattr(response, "get") else 0
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Attack validation failed while checking movies_poisoned poison markers: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    if poison_marked <= 0:
        raise RuntimeError(
            "Attack validation failed: movies_poisoned contains zero poison_marker=true docs. "
            "Rebuild poisoned bulk and reindex before running eval. "
            "Run: uv run --project api python -m api.app.cli.cli attack build-poisoned "
            "&& uv run --project api python -m api.app.cli.cli index poisoned"
        )

    warnings.append(f"Validated poisoned index: poison_marker=true docs={poison_marked}")
    target_validation = _validate_target_poison_state(
        es_client=es_client,
        attack_config=attack_config,
        target_movie_id=target_movie_id,
    )
    if target_validation is not None:
        warnings.append(target_validation)
    return warnings


def _validate_target_poison_state(
    *,
    es_client: Any,
    attack_config: AttackConfig,
    target_movie_id: int | None,
) -> str | None:
    if target_movie_id is None:
        return None
    if attack_config.attack_type not in {"targeted_promotion", "prompt_injection"}:
        return None
    if not hasattr(es_client, "search"):
        return (
            "Target poisoning validation skipped because es_client.search is unavailable; "
            f"cannot confirm target_movie_id={target_movie_id} poison state."
        )

    try:
        response = es_client.search(
            index="movies_poisoned",
            query={"term": {"movie_id": str(target_movie_id)}},
            size=1,
        )
    except Exception as exc:  # noqa: BLE001
        return (
            f"Target poisoning validation failed for target_movie_id={target_movie_id}: "
            f"{type(exc).__name__}: {exc}"
        )

    hits_raw = _response_get(response, "hits", {})
    hits = _response_get(hits_raw, "hits", [])
    if not isinstance(hits, list) or not hits:
        return f"Target poisoning validation warning: target_movie_id={target_movie_id} not found in movies_poisoned."

    first = hits[0]
    source = _response_get(first, "_source", {})
    if not isinstance(source, dict):
        source = {}
    poison_marker = bool(source.get("poison_marker", False))
    poison_payload_present = bool(str(source.get("poison_payload", "") or "").strip())
    synopsis_present = bool(str(source.get("synopsis", "") or "").strip())
    if not poison_marker and not poison_payload_present:
        return (
            f"Target poisoning validation warning: target_movie_id={target_movie_id} present but appears unpoisoned "
            "(poison_marker=false and empty poison_payload)."
        )
    return (
        f"Validated target poison state: target_movie_id={target_movie_id} "
        f"poison_marker={str(poison_marker).lower()} poison_payload_present={str(poison_payload_present).lower()} "
        f"synopsis_present={str(synopsis_present).lower()}"
    )


def _response_get(value: object, key: str, default: Any) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    getter = getattr(value, "get", None)
    if callable(getter):
        try:
            return getter(key, default)
        except Exception:  # noqa: BLE001
            return default
    return default


def _top_k_ids(recommended: list[int], k: int) -> list[int]:
    output: list[int] = []
    seen: set[int] = set()
    for raw in recommended:
        value = int(raw)
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
        if len(output) >= k:
            break
    return output


def _candidate_overlap_at_k(*, baseline_ids: list[int], attacked_ids: list[int], k: int) -> float:
    if k <= 0:
        return 0.0
    left = set(_top_k_ids(baseline_ids, k))
    right = set(_top_k_ids(attacked_ids, k))
    if not left and not right:
        return 1.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / float(len(union))


def _relevant_hits_at_k(*, recommended: list[int], relevant: set[int], k: int) -> int:
    if k <= 0 or not relevant:
        return 0
    top_k = _top_k_ids(recommended, k)
    return len([movie_id for movie_id in top_k if movie_id in relevant])


def _rank_of_target(*, recommended: list[int], target_movie_id: int | None, k: int) -> int | None:
    if target_movie_id is None or k <= 0:
        return None
    for rank, movie_id in enumerate(_top_k_ids(recommended, k), start=1):
        if int(movie_id) == int(target_movie_id):
            return rank
    return None


def _target_rank_lift(*, baseline_rank: int | None, attacked_rank: int | None) -> int | None:
    if baseline_rank is None and attacked_rank is None:
        return None
    if baseline_rank is None:
        return 0
    if attacked_rank is None:
        return 0
    return int(baseline_rank - attacked_rank)


def _aggregate_target_retrieval(*, per_user_rows: list[dict[str, Any]], target_movie_id: int | None) -> dict[str, Any]:
    if target_movie_id is None:
        return {
            "applicable": False,
            "target_movie_id": None,
            "users": int(len(per_user_rows)),
        }

    total_users = len(per_user_rows)
    baseline_present = 0
    attacked_present = 0
    defended_present = 0
    rank_changed = 0
    defense_rank_changed = 0
    baseline_ranks: list[int] = []
    attacked_ranks: list[int] = []
    defended_ranks: list[int] = []
    lifts: list[int] = []
    defense_lifts: list[int] = []

    for row in per_user_rows:
        baseline_rank_raw = row.get("target_retrieval_rank_baseline")
        attacked_rank_raw = row.get("target_retrieval_rank_attacked")
        defended_rank_raw = row.get("target_retrieval_rank_defended")
        lift_raw = row.get("target_retrieval_rank_lift")
        defense_lift_raw = row.get("target_retrieval_defense_lift")

        baseline_rank = int(baseline_rank_raw) if isinstance(baseline_rank_raw, int) else None
        attacked_rank = int(attacked_rank_raw) if isinstance(attacked_rank_raw, int) else None
        defended_rank = int(defended_rank_raw) if isinstance(defended_rank_raw, int) else None
        lift = int(lift_raw) if isinstance(lift_raw, int) else None
        defense_lift = int(defense_lift_raw) if isinstance(defense_lift_raw, int) else None

        if baseline_rank is not None:
            baseline_present += 1
            baseline_ranks.append(baseline_rank)
        if attacked_rank is not None:
            attacked_present += 1
            attacked_ranks.append(attacked_rank)
        if defended_rank is not None:
            defended_present += 1
            defended_ranks.append(defended_rank)
        if baseline_rank != attacked_rank:
            rank_changed += 1
        if attacked_rank != defended_rank:
            defense_rank_changed += 1
        if lift is not None:
            lifts.append(lift)
        if defense_lift is not None:
            defense_lifts.append(defense_lift)

    baseline_presence_rate = (baseline_present / float(total_users)) if total_users > 0 else 0.0
    attacked_presence_rate = (attacked_present / float(total_users)) if total_users > 0 else 0.0
    defended_presence_rate = (defended_present / float(total_users)) if total_users > 0 else 0.0
    mean_baseline_rank = (sum(baseline_ranks) / float(len(baseline_ranks))) if baseline_ranks else None
    mean_attacked_rank = (sum(attacked_ranks) / float(len(attacked_ranks))) if attacked_ranks else None
    mean_defended_rank = (sum(defended_ranks) / float(len(defended_ranks))) if defended_ranks else None
    mean_lift = (sum(lifts) / float(len(lifts))) if lifts else None
    mean_defense_lift = (sum(defense_lifts) / float(len(defense_lifts))) if defense_lifts else None

    output = {
        "applicable": True,
        "target_movie_id": int(target_movie_id),
        "users": int(total_users),
        "target_in_retrieval_baseline_users": int(baseline_present),
        "target_in_retrieval_attacked_users": int(attacked_present),
        "target_in_retrieval_baseline_rate": round(float(baseline_presence_rate), 6),
        "target_in_retrieval_attacked_rate": round(float(attacked_presence_rate), 6),
        "target_retrieval_rank_changed_users": int(rank_changed),
        "target_retrieval_rank_changed_rate": round((rank_changed / float(total_users)) if total_users > 0 else 0.0, 6),
        "target_retrieval_mean_rank_baseline": round(float(mean_baseline_rank), 6)
        if mean_baseline_rank is not None
        else None,
        "target_retrieval_mean_rank_attacked": round(float(mean_attacked_rank), 6)
        if mean_attacked_rank is not None
        else None,
        "target_retrieval_mean_rank_lift": round(float(mean_lift), 6) if mean_lift is not None else None,
    }
    if defended_ranks or any("target_in_retrieval_defended" in row for row in per_user_rows):
        output["target_in_retrieval_defended_users"] = int(defended_present)
        output["target_in_retrieval_defended_rate"] = round(float(defended_presence_rate), 6)
        output["target_retrieval_defense_rank_changed_users"] = int(defense_rank_changed)
        output["target_retrieval_defense_rank_changed_rate"] = round(
            (defense_rank_changed / float(total_users)) if total_users > 0 else 0.0,
            6,
        )
        output["target_retrieval_mean_rank_defended"] = (
            round(float(mean_defended_rank), 6) if mean_defended_rank is not None else None
        )
        output["target_retrieval_mean_rank_defense_lift"] = (
            round(float(mean_defense_lift), 6) if mean_defense_lift is not None else None
        )
    return output


def _round_metrics(values: dict[str, float]) -> dict[str, float]:
    return {key: round(float(value), 6) for key, value in values.items()}


def _is_asr_applicable(*, attack_type: str, target_movie_id: int | None) -> bool:
    if target_movie_id is None:
        return False
    return attack_type in {"targeted_promotion", "prompt_injection"}


def _asr_applicability_reason(*, attack_type: str, target_movie_id: int | None) -> str:
    if target_movie_id is None:
        return "target_movie_id_not_configured"
    if attack_type == "targeted_promotion":
        return "targeted_promotion_with_target"
    if attack_type == "prompt_injection":
        return "prompt_injection_with_target"
    return f"attack_type={attack_type} configured as non-targeted for ASR"


def _normalize_label(label: str) -> str:
    trimmed = label.strip()
    if trimmed == "":
        raise ValueError("label must not be empty")
    safe = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in trimmed)
    safe = safe.strip("_")
    if safe == "":
        raise ValueError("label must contain at least one alphanumeric character")
    return safe


def _default_run_label() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("run_%Y%m%d_%H%M%S")


def _validate_eval_victim_llm_config(
    *,
    llm_config: LlmConfig,
    settings: Settings,
    llm_registry: LlmRegistry,
) -> None:
    if llm_config.ranking_mode != "llm_rerank":
        return

    provider = llm_config.victim.provider
    model = llm_config.victim.model
    base_url = settings.ollama_base_url

    try:
        client = llm_registry.get_victim_client()
    except Exception as exc:  # noqa: BLE001
        message = f"Victim LLM preflight failed: provider={provider}, model={model}"
        if provider == "local":
            message += f", base_url={base_url}"
        message += f". Unable to initialize client: {type(exc).__name__}: {exc}"
        raise RuntimeError(message) from exc

    if provider == "local":
        if not llm_registry.ollama_connectivity():
            message = (
                "Victim LLM preflight failed: "
                f"provider={provider}, model={model}, base_url={base_url}. Ollama is unreachable."
            )
            host = (urlparse(base_url).hostname or "").strip().lower()
            if host == "ollama":
                message += " Hint: Set OLLAMA_BASE_URL=http://localhost:11434 when running uv on host."
            raise RuntimeError(message)

        available_models = llm_registry.list_local_models()
        if model not in available_models:
            raise RuntimeError(
                "Victim LLM preflight failed: "
                f"provider={provider}, model={model}, base_url={base_url}. "
                f"Model '{model}' not found at {base_url}. Run: ollama pull {model}"
            )
        return

    status = client.healthcheck()
    if not status.available or not status.healthy:
        reason = status.message.strip() or "Provider healthcheck failed."
        raise RuntimeError(f"Victim LLM preflight failed: provider={provider}, model={model}. {reason}")
