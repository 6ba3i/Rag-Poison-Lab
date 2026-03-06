from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import random
from typing import Any, Literal
from urllib.parse import urlparse

from api.app.eval.metrics import asr_at_k, hr_at_k, mean_metrics, metrics_delta, mrr_at_k, ndcg_at_k
from api.app.llm.registry import LlmRegistry
from api.app.services.recs_service import RecsService, load_llm_config
from api.app.services.users_service import UsersService
from api.app.settings import Settings, get_es_client, get_settings
from common.schemas.attack_config import AttackConfig, load_attack_config
from common.schemas.llm_config import LlmConfig

EvalMode = Literal["single", "batch", "full"]
BASE_METRIC_KEYS: tuple[str, ...] = ("hr", "ndcg", "mrr")
ASR_METRIC_KEY = "asr"
AUTO_TARGET_POOL_SIZE = 20
AUTO_TARGET_PICK_SEED = 42


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
) -> dict[str, Any]:
    if k <= 0:
        raise ValueError("k must be >= 1")
    if batch_size <= 0:
        raise ValueError("batch_size must be >= 1")

    resolved_settings = settings or get_settings()
    resolved_es_client = es_client if es_client is not None else get_es_client()
    llm_registry = LlmRegistry(settings=resolved_settings)

    users_service = UsersService(settings=resolved_settings)
    recs_service = RecsService(settings=resolved_settings, es_client=resolved_es_client, llm_registry=llm_registry)

    selected_user_ids = _resolve_user_ids(
        users_service=users_service,
        mode=mode,
        user_id=user_id,
        batch_size=batch_size,
    )

    relevant_by_user = _build_relevant_movies_map(users_service)
    llm_config = load_llm_config(settings=resolved_settings)
    _validate_eval_victim_llm_config(
        llm_config=llm_config,
        settings=resolved_settings,
        llm_registry=llm_registry,
    )

    attack_config = load_attack_config((resolved_settings.resolved_config_dir / "attack_config.json").resolve())
    target_movie_id, eval_warnings, target_movie_source = _resolve_target_movie_id(
        attack_config=attack_config,
        users_service=users_service,
    )
    eval_warnings.extend(_validate_poisoned_index_state(es_client=resolved_es_client, attack_config=attack_config))
    asr_applicable = bool(attack_config.attack_type == "targeted_promotion" and target_movie_id is not None)
    metric_keys: tuple[str, ...] = BASE_METRIC_KEYS + ((ASR_METRIC_KEY,) if asr_applicable else tuple())

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
            if mode == "single":
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
                baseline = baseline_result["items"]
                attacked = attacked_result["items"]
            else:
                baseline = recs_service.recommend(
                    user_id=current_user_id,
                    mode="baseline",
                    k=k,
                    seen_history_split="train",
                    strict_retrieval=True,
                )
                attacked = recs_service.recommend(
                    user_id=current_user_id,
                    mode="attacked",
                    k=k,
                    seen_history_split="train",
                    strict_retrieval=True,
                )
                baseline_result = {"debug": None}
                attacked_result = {"debug": None}
        except Exception as exc:  # noqa: BLE001
            skipped.append({"user_id": current_user_id, "reason": f"recommendation_error: {exc}"})
            continue

        baseline_ids = _extract_movie_ids(baseline)
        attacked_ids = _extract_movie_ids(attacked)

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
        if asr_applicable:
            baseline_metrics[ASR_METRIC_KEY] = asr_at_k(baseline_ids, target_movie_id, k)
            attacked_metrics[ASR_METRIC_KEY] = asr_at_k(attacked_ids, target_movie_id, k)

        overlap = _candidate_overlap_at_k(baseline_ids=baseline_ids, attacked_ids=attacked_ids, k=k)
        target_rank_baseline = _rank_of_target(recommended=baseline_ids, target_movie_id=target_movie_id, k=k)
        target_rank_attacked = _rank_of_target(recommended=attacked_ids, target_movie_id=target_movie_id, k=k)
        target_rank_lift = _target_rank_lift(
            baseline_rank=target_rank_baseline,
            attacked_rank=target_rank_attacked,
        )

        per_user_rows.append(
            {
                "user_id": current_user_id,
                "relevant_test_count": len(relevant),
                "candidate_overlap_at_k": round(overlap, 6),
                "target_rank_baseline": target_rank_baseline,
                "target_rank_attacked": target_rank_attacked,
                "target_rank_lift": target_rank_lift,
                "baseline": _round_metrics(baseline_metrics),
                "attacked": _round_metrics(attacked_metrics),
                "delta": _round_metrics(metrics_delta(baseline=baseline_metrics, attacked=attacked_metrics)),
            }
        )

        if mode == "single":
            attack_trace_payload = {
                "mode": mode,
                "user_id": int(current_user_id),
                "k": int(k),
                "attack_config": attack_config.model_dump(),
                "target_movie_id": int(target_movie_id) if target_movie_id is not None else None,
                "target_movie_source": target_movie_source,
                "asr_applicable": asr_applicable,
                "baseline_index": "movies",
                "attacked_index": "movies_poisoned",
                "relevant_test_movie_ids": sorted(int(item) for item in relevant),
                "baseline_debug": baseline_result.get("debug"),
                "attacked_debug": attacked_result.get("debug"),
                "metrics_input": {
                    "baseline_ids": baseline_ids,
                    "attacked_ids": attacked_ids,
                    "baseline_metrics": _round_metrics(baseline_metrics),
                    "attacked_metrics": _round_metrics(attacked_metrics),
                    "delta_metrics": _round_metrics(metrics_delta(baseline=baseline_metrics, attacked=attacked_metrics)),
                    "candidate_overlap_at_k": round(overlap, 6),
                    "target_rank_baseline": target_rank_baseline,
                    "target_rank_attacked": target_rank_attacked,
                    "target_rank_lift": target_rank_lift,
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

    run_label = _normalize_label(label) if label is not None else _default_run_label()
    run_dir = resolve_run_dir(settings=resolved_settings, label=run_label, results_root=results_root)
    run_dir.mkdir(parents=True, exist_ok=True)
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
            "asr_applicable_reason": (
                "targeted_promotion_with_target"
                if asr_applicable
                else f"attack_type={attack_config.attack_type} does not use ASR as primary success metric"
            ),
            "metric_keys": list(metric_keys),
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        },
        "baseline": baseline_aggregate,
        "attacked": attacked_aggregate,
        "delta": delta_aggregate,
        "per_user": per_user_rows,
        "skipped": skipped,
    }
    if eval_warnings:
        payload["warnings"] = list(eval_warnings)
    if attack_trace_path is not None:
        payload["attack_trace_path"] = str(attack_trace_path)

    metrics_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

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
        "target_movie_id": int(target_movie_id) if target_movie_id is not None else None,
        "target_movie_source": target_movie_source,
        "asr_applicable": asr_applicable,
        "metric_keys": list(metric_keys),
    }
    if eval_warnings:
        summary["warnings"] = list(eval_warnings)
    if attack_trace_path is not None:
        summary["attack_trace_path"] = str(attack_trace_path)
    return summary


def resolve_run_dir(*, settings: Settings, label: str, results_root: Path | None = None) -> Path:
    base = results_root.resolve() if results_root is not None else (settings.resolved_data_root / "results" / "runs")
    return (base / label).resolve()


def _resolve_user_ids(
    *,
    users_service: UsersService,
    mode: EvalMode,
    user_id: int | None,
    batch_size: int,
) -> list[int]:
    all_users = users_service.list_users(limit=1_000_000)
    ordered_ids = sorted(int(item["user_id"]) for item in all_users)

    if mode == "single":
        if user_id is None:
            raise ValueError("user_id is required when mode=single")
        if int(user_id) not in set(ordered_ids):
            raise ValueError(f"Unknown user_id: {user_id}")
        return [int(user_id)]

    if mode == "batch":
        return ordered_ids[:batch_size]

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


def _resolve_target_movie_id(
    *,
    attack_config: AttackConfig,
    users_service: UsersService,
) -> tuple[int | None, list[str], str]:
    configured_target = attack_config.target_movie_id
    if configured_target is not None:
        return int(configured_target), [], "configured"

    if attack_config.attack_type != "targeted_promotion":
        return None, [], "none"

    selected = _auto_pick_target_movie_id(users_service=users_service)
    warnings = [
        "target_movie_id is not set for attack_type=targeted_promotion; "
        f"auto-selected deterministic target_movie_id={selected} (seed={AUTO_TARGET_PICK_SEED}). "
        "Set data/config/attack_config.json:target_movie_id to avoid automatic selection."
    ]
    return selected, warnings, "auto_selected"


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


def _validate_poisoned_index_state(*, es_client: Any, attack_config: AttackConfig) -> list[str]:
    if float(attack_config.poison_fraction) <= 0.0:
        return []
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
    return [f"Validated poisoned index: poison_marker=true docs={poison_marked}"]


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


def _round_metrics(values: dict[str, float]) -> dict[str, float]:
    return {key: round(float(value), 6) for key, value in values.items()}


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
