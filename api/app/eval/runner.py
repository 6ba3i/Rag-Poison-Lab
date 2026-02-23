from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from api.app.eval.metrics import asr_at_k, hr_at_k, mean_metrics, metrics_delta, mrr_at_k, ndcg_at_k
from api.app.llm.registry import LlmRegistry
from api.app.services.recs_service import RecsService, load_llm_config
from api.app.services.users_service import UsersService
from api.app.settings import Settings, get_es_client, get_settings
from common.schemas.attack_config import load_attack_config
from common.schemas.llm_config import LlmConfig

EvalMode = Literal["single", "batch", "full"]
METRIC_KEYS: tuple[str, ...] = ("hr", "ndcg", "mrr", "asr")


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
    target_movie_id = attack_config.target_movie_id

    per_user_rows: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for current_user_id in selected_user_ids:
        relevant = relevant_by_user.get(current_user_id, set())
        if not relevant:
            skipped.append({"user_id": current_user_id, "reason": "no_test_items"})
            continue

        try:
            baseline = recs_service.recommend(user_id=current_user_id, mode="baseline", k=k)
            attacked = recs_service.recommend(user_id=current_user_id, mode="attacked", k=k)
        except Exception as exc:  # noqa: BLE001
            skipped.append({"user_id": current_user_id, "reason": f"recommendation_error: {exc}"})
            continue

        baseline_ids = _extract_movie_ids(baseline)
        attacked_ids = _extract_movie_ids(attacked)

        baseline_metrics = {
            "hr": hr_at_k(baseline_ids, relevant, k),
            "ndcg": ndcg_at_k(baseline_ids, relevant, k),
            "mrr": mrr_at_k(baseline_ids, relevant, k),
            "asr": asr_at_k(baseline_ids, target_movie_id, k),
        }
        attacked_metrics = {
            "hr": hr_at_k(attacked_ids, relevant, k),
            "ndcg": ndcg_at_k(attacked_ids, relevant, k),
            "mrr": mrr_at_k(attacked_ids, relevant, k),
            "asr": asr_at_k(attacked_ids, target_movie_id, k),
        }

        per_user_rows.append(
            {
                "user_id": current_user_id,
                "relevant_test_count": len(relevant),
                "baseline": _round_metrics(baseline_metrics),
                "attacked": _round_metrics(attacked_metrics),
                "delta": _round_metrics(metrics_delta(baseline=baseline_metrics, attacked=attacked_metrics)),
            }
        )

    if not per_user_rows:
        raise RuntimeError(
            "No users were evaluated. Ensure processed files exist and selected users have test split rows."
        )

    baseline_aggregate = _round_metrics(
        mean_metrics([row["baseline"] for row in per_user_rows], METRIC_KEYS)
    )
    attacked_aggregate = _round_metrics(
        mean_metrics([row["attacked"] for row in per_user_rows], METRIC_KEYS)
    )
    delta_aggregate = _round_metrics(metrics_delta(baseline=baseline_aggregate, attacked=attacked_aggregate))

    run_label = _normalize_label(label) if label is not None else _default_run_label()
    run_dir = resolve_run_dir(settings=resolved_settings, label=run_label, results_root=results_root)
    run_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = run_dir / "metrics.json"

    payload: dict[str, Any] = {
        "label": run_label,
        "mode": mode,
        "k": int(k),
        "requested_users": len(selected_user_ids),
        "evaluated_users": len(per_user_rows),
        "skipped_users": len(skipped),
        "metadata": {
            "target_movie_id": int(target_movie_id) if target_movie_id is not None else None,
            "asr_applicable": bool(target_movie_id is not None),
            "metric_keys": list(METRIC_KEYS),
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        },
        "baseline": baseline_aggregate,
        "attacked": attacked_aggregate,
        "delta": delta_aggregate,
        "per_user": per_user_rows,
        "skipped": skipped,
    }

    metrics_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return {
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
    }


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
