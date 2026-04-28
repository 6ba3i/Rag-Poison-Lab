from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from api.app.data.paths import ES_BULK_MOVIES_JSONL, ES_BULK_POISONED_MOVIES_JSONL
from api.app.eval.runner import resolve_run_dir
from api.app.services.recs_service import RecsService, load_llm_config, recommendation_retrieval_size
from api.app.services.users_service import UsersService
from api.app.settings import Settings, get_es_client, get_settings
from common.schemas.attack_config import AttackConfig, load_attack_config
from common.utils.genres import normalize_genres
from rag.recsys.candidate_gen import build_es_query, build_retrieval_query, build_user_context, parse_hits

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _RunContext:
    run_dir: Path
    label: str
    metrics_path: Path | None
    attack_trace_path: Path | None


def generate_audit_artifacts(
    *,
    label: str | None = None,
    run_dir: Path | None = None,
    user_id: int | None = None,
    settings: Settings | None = None,
    es_client: Any | None = None,
    results_root: Path | None = None,
) -> dict[str, Any]:
    resolved_settings = settings or get_settings()
    resolved_es = es_client if es_client is not None else get_es_client()
    users_service = UsersService(settings=resolved_settings)
    recs_service = RecsService(settings=resolved_settings, es_client=resolved_es)
    attack_config = load_attack_config((resolved_settings.resolved_config_dir / "attack_config.json").resolve())
    llm_config = load_llm_config(settings=resolved_settings)
    ctx = _resolve_run_context(
        settings=resolved_settings,
        label=label,
        run_dir=run_dir,
        results_root=results_root,
    )
    target_user_id = _resolve_user_id(
        user_id=user_id,
        users_service=users_service,
        attack_trace_path=ctx.attack_trace_path,
    )

    baseline_bulk_path = resolved_settings.resolved_processed_dir / ES_BULK_MOVIES_JSONL
    poisoned_bulk_path = resolved_settings.resolved_processed_dir / ES_BULK_POISONED_MOVIES_JSONL
    baseline_bulk_docs = _read_bulk_docs(baseline_bulk_path)
    poisoned_bulk_docs = _read_bulk_docs(poisoned_bulk_path)
    bulk_diff = _bulk_diff_summary(
        baseline_docs=baseline_bulk_docs,
        poisoned_docs=poisoned_bulk_docs,
        target_movie_id=attack_config.target_movie_id,
    )

    index_diff = _index_diff_summary(
        es_client=resolved_es,
        attack_config=attack_config,
        target_movie_id=attack_config.target_movie_id,
    )
    retrieval_diff = _retrieval_diff_summary(
        users_service=users_service,
        recs_service=recs_service,
        es_client=resolved_es,
        llm_config=llm_config,
        user_id=target_user_id,
    )
    metrics_diagnosis = _metrics_diagnosis(
        metrics_path=ctx.metrics_path,
        attack_trace_path=ctx.attack_trace_path,
        user_id=target_user_id,
    )
    root_causes = _root_cause_hypotheses(
        attack_config=attack_config,
        bulk_diff=bulk_diff,
        retrieval_diff=retrieval_diff,
        metrics_diagnosis=metrics_diagnosis,
    )

    call_graph = _call_graph()
    bug_list = _bug_list(root_causes=root_causes)
    fix_plan = _fix_plan(root_causes=root_causes)
    logging_plan = _logging_plan()
    validation_checklist = _validation_checklist()
    report_md = _audit_report_markdown(
        ctx=ctx,
        attack_config=attack_config,
        llm_ranking_mode=llm_config.ranking_mode,
        user_id=target_user_id,
        bulk_diff=bulk_diff,
        retrieval_diff=retrieval_diff,
        metrics_diagnosis=metrics_diagnosis,
        root_causes=root_causes,
    )

    audit_dir = (ctx.run_dir / "audit").resolve()
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit_report_path = _write_text(audit_dir / "audit_report.md", report_md)
    bug_list_path = _write_text(audit_dir / "bug_list.md", _to_markdown_list("Bug List", bug_list))
    fix_plan_path = _write_text(audit_dir / "fix_plan.md", _to_markdown_list("Fix Plan", fix_plan))
    logging_plan_path = _write_text(audit_dir / "logging_plan.md", _to_markdown_list("Logging Plan", logging_plan))
    validation_path = _write_text(
        audit_dir / "validation_checklist.md",
        _to_markdown_numbered("Validation Checklist", validation_checklist),
    )
    call_graph_path = _write_json(audit_dir / "call_graph.json", call_graph)
    index_diff_path = _write_json(audit_dir / "index_diff.json", index_diff)
    retrieval_diff_path = _write_json(audit_dir / "retrieval_diff.json", retrieval_diff)
    metrics_diag_path = _write_json(audit_dir / "metrics_diagnosis.json", metrics_diagnosis)

    summary = {
        "label": ctx.label,
        "run_dir": str(ctx.run_dir),
        "audit_dir": str(audit_dir),
        "audit_report_path": str(audit_report_path),
        "bug_list_path": str(bug_list_path),
        "fix_plan_path": str(fix_plan_path),
        "logging_plan_path": str(logging_plan_path),
        "validation_checklist_path": str(validation_path),
        "call_graph_path": str(call_graph_path),
        "index_diff_path": str(index_diff_path),
        "retrieval_diff_path": str(retrieval_diff_path),
        "metrics_diagnosis_path": str(metrics_diag_path),
        "user_id": int(target_user_id),
    }
    logger.info(
        "audit_artifacts_generated run_label=%s run_dir=%s audit_dir=%s user_id=%s",
        ctx.label,
        ctx.run_dir,
        audit_dir,
        target_user_id,
    )
    return summary


def _resolve_run_context(
    *,
    settings: Settings,
    label: str | None,
    run_dir: Path | None,
    results_root: Path | None,
) -> _RunContext:
    if run_dir is not None:
        resolved = run_dir.resolve()
    elif label is not None:
        resolved = resolve_run_dir(settings=settings, label=label, results_root=results_root)
    else:
        base = results_root.resolve() if results_root is not None else (settings.resolved_data_root / "results" / "runs")
        resolved = _latest_run_dir(base)

    resolved.mkdir(parents=True, exist_ok=True)
    label_value = resolved.name
    metrics_path = resolved / "metrics.json"
    trace_path = resolved / "attack_trace.json"
    return _RunContext(
        run_dir=resolved,
        label=label_value,
        metrics_path=metrics_path if metrics_path.exists() else None,
        attack_trace_path=trace_path if trace_path.exists() else None,
    )


def _latest_run_dir(base: Path) -> Path:
    if not base.exists() or not base.is_dir():
        raise FileNotFoundError(f"Results directory not found: {base}")
    candidates = [entry for entry in base.iterdir() if entry.is_dir()]
    if not candidates:
        raise FileNotFoundError(f"No run directories found under: {base}")
    return sorted(candidates, key=lambda path: path.name)[-1]


def _resolve_user_id(*, user_id: int | None, users_service: UsersService, attack_trace_path: Path | None) -> int:
    if user_id is not None:
        return int(user_id)
    if attack_trace_path is not None:
        payload = _read_json(attack_trace_path)
        trace_user = payload.get("user_id")
        if isinstance(trace_user, int):
            return int(trace_user)
    users = users_service.list_users(limit=1)
    if not users:
        raise RuntimeError("Unable to resolve audit user_id: users dataset is empty.")
    return int(users[0]["user_id"])


def _read_bulk_docs(path: Path) -> list[dict[str, Any]]:
    if not path.exists() or path.stat().st_size == 0:
        raise FileNotFoundError(f"Bulk file missing or empty: {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) % 2 != 0:
        raise ValueError(f"Bulk file has invalid line count (expected action/document pairs): {path}")
    docs: list[dict[str, Any]] = []
    for idx in range(0, len(lines), 2):
        docs.append(json.loads(lines[idx + 1]))
    return docs


def _bulk_diff_summary(
    *,
    baseline_docs: list[dict[str, Any]],
    poisoned_docs: list[dict[str, Any]],
    target_movie_id: int | None,
) -> dict[str, Any]:
    baseline_by_id = {str(doc.get("movie_id", "")).strip(): doc for doc in baseline_docs}
    poisoned_by_id = {str(doc.get("movie_id", "")).strip(): doc for doc in poisoned_docs}

    changed_title = 0
    changed_genres = 0
    changed_synopsis = 0
    changed_any_nonpoison = 0
    changed_only_poison = 0
    poison_marker_true = 0
    poison_payload_nonempty = 0
    sample_changed: list[dict[str, Any]] = []
    for movie_id, poisoned in poisoned_by_id.items():
        baseline = baseline_by_id.get(movie_id, {})
        title_changed = str(baseline.get("title", "") or "").strip() != str(poisoned.get("title", "") or "").strip()
        genres_changed = normalize_genres(baseline.get("genres", [])) != normalize_genres(poisoned.get("genres", []))
        synopsis_changed = str(baseline.get("synopsis", "") or "").strip() != str(poisoned.get("synopsis", "") or "").strip()
        marker_changed = bool(baseline.get("poison_marker", False)) != bool(poisoned.get("poison_marker", False))
        payload_changed = (
            str(baseline.get("poison_payload", "") or "").strip() != str(poisoned.get("poison_payload", "") or "").strip()
        )
        if title_changed:
            changed_title += 1
        if genres_changed:
            changed_genres += 1
        if synopsis_changed:
            changed_synopsis += 1
        if title_changed or genres_changed or synopsis_changed:
            changed_any_nonpoison += 1
        elif marker_changed or payload_changed:
            changed_only_poison += 1

        if bool(poisoned.get("poison_marker", False)):
            poison_marker_true += 1
        if str(poisoned.get("poison_payload", "") or "").strip():
            poison_payload_nonempty += 1

        if len(sample_changed) < 10 and (title_changed or genres_changed or synopsis_changed or marker_changed or payload_changed):
            changed_fields: list[str] = []
            if title_changed:
                changed_fields.append("title")
            if genres_changed:
                changed_fields.append("genres")
            if synopsis_changed:
                changed_fields.append("synopsis")
            if marker_changed:
                changed_fields.append("poison_marker")
            if payload_changed:
                changed_fields.append("poison_payload")
            sample_changed.append(
                {
                    "movie_id": movie_id,
                    "changed_fields": changed_fields,
                    "synopsis_before": str(baseline.get("synopsis", "") or "")[:120],
                    "synopsis_after": str(poisoned.get("synopsis", "") or "")[:120],
                    "poison_payload_after": str(poisoned.get("poison_payload", "") or "")[:120],
                }
            )

    target_doc = poisoned_by_id.get(str(target_movie_id)) if target_movie_id is not None else None
    target_poisoned = bool(target_doc and (target_doc.get("poison_marker", False) or str(target_doc.get("poison_payload", "")).strip()))
    return {
        "baseline_docs": len(baseline_docs),
        "poisoned_docs": len(poisoned_docs),
        "poison_marker_true_docs": poison_marker_true,
        "poison_payload_nonempty_docs": poison_payload_nonempty,
        "changed_title": changed_title,
        "changed_genres": changed_genres,
        "changed_synopsis": changed_synopsis,
        "changed_any_nonpoison_fields": changed_any_nonpoison,
        "changed_only_poison_fields": changed_only_poison,
        "target_movie_id": target_movie_id,
        "target_is_poisoned": target_poisoned,
        "sample_changed_docs": sample_changed,
    }


def _index_diff_summary(
    *,
    es_client: Any,
    attack_config: AttackConfig,
    target_movie_id: int | None,
) -> dict[str, Any]:
    output: dict[str, Any] = {
        "attack_type": attack_config.attack_type,
        "target_movie_id": target_movie_id,
    }
    for index_name in ("movies", "movies_poisoned"):
        count_value: int | None = None
        mapping: dict[str, Any] | None = None
        target_doc: dict[str, Any] | None = None
        try:
            count_resp = es_client.count(index=index_name)
            count_raw = _response_get(count_resp, "count", None)
            if count_raw is not None:
                count_value = int(count_raw)
        except Exception as exc:  # noqa: BLE001
            output[f"{index_name}_count_error"] = f"{type(exc).__name__}: {exc}"

        try:
            mapping_resp = es_client.indices.get_mapping(index=index_name)
            mapping = _response_to_dict(mapping_resp)
        except Exception as exc:  # noqa: BLE001
            output[f"{index_name}_mapping_error"] = f"{type(exc).__name__}: {exc}"

        if target_movie_id is not None:
            try:
                search_resp = es_client.search(
                    index=index_name,
                    query={"term": {"movie_id": str(target_movie_id)}},
                    size=1,
                )
                hits_raw = _response_get(search_resp, "hits", {})
                hits = _response_get(hits_raw, "hits", [])
                if isinstance(hits, list) and hits:
                    first = hits[0]
                    if isinstance(first, dict):
                        source = first.get("_source", {})
                        target_doc = source if isinstance(source, dict) else None
            except Exception as exc:  # noqa: BLE001
                output[f"{index_name}_target_lookup_error"] = f"{type(exc).__name__}: {exc}"

        output[index_name] = {
            "doc_count": count_value,
            "mapping_properties": _mapping_properties(mapping),
            "target_doc": target_doc,
        }

    try:
        poison_resp = es_client.count(index="movies_poisoned", query={"term": {"poison_marker": True}})
        poison_raw = _response_get(poison_resp, "count", None)
        output["movies_poisoned_poison_marker_true"] = int(poison_raw) if poison_raw is not None else None
    except Exception as exc:  # noqa: BLE001
        output["movies_poisoned_poison_marker_error"] = f"{type(exc).__name__}: {exc}"
    return output


def _mapping_properties(mapping: dict[str, Any] | None) -> dict[str, Any] | None:
    if mapping is None:
        return None
    for value in mapping.values():
        if isinstance(value, dict):
            mappings = value.get("mappings")
            if isinstance(mappings, dict):
                props = mappings.get("properties")
                if isinstance(props, dict):
                    return props
    return None


def _response_get(value: object, key: str, default: object) -> object:
    if isinstance(value, dict):
        return value.get(key, default)
    getter = getattr(value, "get", None)
    if callable(getter):
        try:
            return getter(key, default)
        except Exception:  # noqa: BLE001
            return default
    return default


def _response_to_dict(value: object) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    body = getattr(value, "body", None)
    if isinstance(body, dict):
        return body
    as_dict = getattr(value, "_asdict", None)
    if callable(as_dict):
        try:
            converted = as_dict()
            if isinstance(converted, dict):
                return converted
        except Exception:  # noqa: BLE001
            return None
    return None


def _retrieval_diff_summary(
    *,
    users_service: UsersService,
    recs_service: RecsService,
    es_client: Any,
    llm_config: Any,
    user_id: int,
) -> dict[str, Any]:
    profile = users_service.get_profile(user_id)
    if profile is None:
        raise KeyError(f"Unknown user_id for audit: {user_id}")
    history_train = users_service.get_history(user_id, split="train")
    seen_movie_ids = {item["movie_id"] for item in history_train}
    context = build_user_context(profile=profile, train_history=history_train)
    query_text = build_retrieval_query(context)
    query_body = build_es_query(query_text=query_text, seen_movie_ids=seen_movie_ids)
    size = recommendation_retrieval_size(ranking_mode=llm_config.ranking_mode, k=10)

    baseline_search = es_client.search(index="movies", query=query_body, size=size)
    attacked_search = es_client.search(index="movies_poisoned", query=query_body, size=size)
    baseline_hits = _response_get(_response_get(baseline_search, "hits", {}), "hits", [])
    attacked_hits = _response_get(_response_get(attacked_search, "hits", {}), "hits", [])
    if not isinstance(baseline_hits, list):
        baseline_hits = []
    if not isinstance(attacked_hits, list):
        attacked_hits = []

    baseline_candidates = parse_hits(hits=baseline_hits, seen_movie_ids=seen_movie_ids)
    attacked_candidates = parse_hits(hits=attacked_hits, seen_movie_ids=seen_movie_ids)
    baseline_ids = [item.movie_id for item in baseline_candidates]
    attacked_ids = [item.movie_id for item in attacked_candidates]
    baseline_scores = [round(float(item.bm25_score), 6) for item in baseline_candidates]
    attacked_scores = [round(float(item.bm25_score), 6) for item in attacked_candidates]

    baseline_debug = recs_service.recommend_with_debug(
        user_id=user_id,
        mode="baseline",
        k=10,
        seen_history_split="train",
        strict_retrieval=True,
    )["debug"]
    attacked_debug = recs_service.recommend_with_debug(
        user_id=user_id,
        mode="attacked",
        k=10,
        seen_history_split="train",
        strict_retrieval=True,
    )["debug"]

    baseline_set = set(baseline_ids)
    attacked_set = set(attacked_ids)
    union = baseline_set | attacked_set
    jaccard = 1.0 if not union else len(baseline_set & attacked_set) / float(len(union))
    return {
        "user_id": user_id,
        "query_text": query_text,
        "query_body": query_body,
        "ranking_mode": llm_config.ranking_mode,
        "retrieval_size": size,
        "baseline_index": "movies",
        "attacked_index": "movies_poisoned",
        "baseline_candidate_ids": baseline_ids,
        "attacked_candidate_ids": attacked_ids,
        "baseline_candidate_scores": baseline_scores,
        "attacked_candidate_scores": attacked_scores,
        "candidate_set_jaccard": round(jaccard, 6),
        "candidate_ids_equal": baseline_ids == attacked_ids,
        "candidate_scores_equal": baseline_scores == attacked_scores,
        "baseline_debug": baseline_debug,
        "attacked_debug": attacked_debug,
    }


def _metrics_diagnosis(
    *,
    metrics_path: Path | None,
    attack_trace_path: Path | None,
    user_id: int,
) -> dict[str, Any]:
    metrics = _read_json(metrics_path) if metrics_path is not None and metrics_path.exists() else {}
    attack_trace = _read_json(attack_trace_path) if attack_trace_path is not None and attack_trace_path.exists() else {}
    per_user = metrics.get("per_user", []) if isinstance(metrics, dict) else []
    current_user_row: dict[str, Any] | None = None
    if isinstance(per_user, list):
        for row in per_user:
            if isinstance(row, dict) and int(row.get("user_id", -1)) == int(user_id):
                current_user_row = row
                break
    trace_metrics_input = attack_trace.get("metrics_input", {}) if isinstance(attack_trace, dict) else {}
    relevant_ids = attack_trace.get("relevant_test_movie_ids", []) if isinstance(attack_trace, dict) else []
    baseline_ids = trace_metrics_input.get("baseline_ids", []) if isinstance(trace_metrics_input, dict) else []
    attacked_ids = trace_metrics_input.get("attacked_ids", []) if isinstance(trace_metrics_input, dict) else []
    baseline_hits = [item for item in baseline_ids if item in set(relevant_ids)] if isinstance(baseline_ids, list) else []
    attacked_hits = [item for item in attacked_ids if item in set(relevant_ids)] if isinstance(attacked_ids, list) else []
    return {
        "metrics_path": str(metrics_path) if metrics_path is not None else None,
        "attack_trace_path": str(attack_trace_path) if attack_trace_path is not None else None,
        "user_id": user_id,
        "summary_baseline": metrics.get("baseline", {}) if isinstance(metrics, dict) else {},
        "summary_attacked": metrics.get("attacked", {}) if isinstance(metrics, dict) else {},
        "summary_delta": metrics.get("delta", {}) if isinstance(metrics, dict) else {},
        "asr_applicable": metrics.get("metadata", {}).get("asr_applicable") if isinstance(metrics, dict) else None,
        "asr_reason": metrics.get("metadata", {}).get("asr_applicable_reason") if isinstance(metrics, dict) else None,
        "per_user_row": current_user_row,
        "relevant_test_movie_ids": relevant_ids if isinstance(relevant_ids, list) else [],
        "baseline_top_k_hits_on_relevant": baseline_hits,
        "attacked_top_k_hits_on_relevant": attacked_hits,
    }


def _root_cause_hypotheses(
    *,
    attack_config: AttackConfig,
    bulk_diff: dict[str, Any],
    retrieval_diff: dict[str, Any],
    metrics_diagnosis: dict[str, Any],
) -> list[dict[str, Any]]:
    hypotheses: list[dict[str, Any]] = []
    if (
        attack_config.attack_type == "prompt_injection"
        and int(bulk_diff.get("changed_any_nonpoison_fields", 0)) == 0
        and int(bulk_diff.get("changed_only_poison_fields", 0)) > 0
    ):
        hypotheses.append(
            {
                "confidence": "very_high",
                "severity": "critical",
                "title": "Prompt injection produced marker/payload-only changes in this run",
                "evidence": [
                    "attack_type=prompt_injection",
                    f"changed_any_nonpoison_fields={bulk_diff.get('changed_any_nonpoison_fields')}",
                    f"changed_only_poison_fields={bulk_diff.get('changed_only_poison_fields')}",
                ],
            }
        )
    if attack_config.target_movie_id is not None and not bool(bulk_diff.get("target_is_poisoned", False)):
        hypotheses.append(
            {
                "confidence": "very_high",
                "severity": "high",
                "title": "Configured target movie is not poisoned in generated corpus",
                "evidence": [
                    f"target_movie_id={attack_config.target_movie_id}",
                    f"target_is_poisoned={bulk_diff.get('target_is_poisoned')}",
                ],
            }
        )
    per_user_row = metrics_diagnosis.get("per_user_row", {})
    if isinstance(per_user_row, dict):
        if float(per_user_row.get("baseline", {}).get("hr", 0.0)) == 0.0 and float(
            per_user_row.get("attacked", {}).get("hr", 0.0)
        ) == 0.0:
            hypotheses.append(
                {
                    "confidence": "high",
                    "severity": "high",
                    "title": "Evaluation is in a zero-hit floor regime for the selected user",
                    "evidence": [
                        f"baseline_hr={per_user_row.get('baseline', {}).get('hr')}",
                        f"attacked_hr={per_user_row.get('attacked', {}).get('hr')}",
                        f"relevant_test_count={per_user_row.get('relevant_test_count')}",
                    ],
                }
            )
    if bool(retrieval_diff.get("candidate_ids_equal", False)) and bool(retrieval_diff.get("candidate_scores_equal", False)):
        hypotheses.append(
            {
                "confidence": "high",
                "severity": "medium",
                "title": "Baseline and attacked retrieval are identical for the audited query",
                "evidence": [
                    "candidate_ids_equal=true",
                    "candidate_scores_equal=true",
                    f"candidate_set_jaccard={retrieval_diff.get('candidate_set_jaccard')}",
                ],
            }
        )
    if metrics_diagnosis.get("asr_applicable") is False and attack_config.target_movie_id is not None:
        hypotheses.append(
            {
                "confidence": "high",
                "severity": "medium",
                "title": "Target metric (ASR) is disabled despite configured target",
                "evidence": [f"asr_reason={metrics_diagnosis.get('asr_reason')}"],
            }
        )
    return hypotheses


def _call_graph() -> dict[str, Any]:
    return {
        "experiment_wizard_run": [
            "api/app/cli/wizard.py:run_wizard",
            "api/app/cli/wizard.py:_run_experiments_screen",
            "api/app/cli/commands_eval.py:evaluate_run",
            "api/app/eval/runner.py:run_experiments",
        ],
        "attack_generation": [
            "api/app/cli/commands_attack.py:build_poisoned",
            "agent/datasets/poison_builder.py:build_poisoned_bulk",
            "agent/attacks/poison_index.py:apply_poisoning",
        ],
        "indexing_baseline_and_poisoned": [
            "api/app/cli/commands_index.py:index_baseline/index_poisoned",
            "api/app/services/indexing_service.py:index_baseline_direct/index_poisoned_direct",
            "api/app/services/indexing_service.py:_bulk_index",
        ],
        "recommendation_baseline_and_attacked": [
            "api/app/eval/runner.py:run_experiments",
            "api/app/services/recs_service.py:recommend_with_debug",
            "rag/recsys/candidate_gen.py:search_candidates",
            "rag/recsys/ranker.py:rank_candidates",
        ],
        "evaluation_metrics_and_trace": [
            "api/app/eval/runner.py:run_experiments",
            "api/app/eval/metrics.py:hr_at_k/ndcg_at_k/mrr_at_k/asr_at_k",
        ],
    }


def _bug_list(*, root_causes: list[dict[str, Any]]) -> list[str]:
    output: list[str] = []
    for idx, item in enumerate(root_causes, start=1):
        output.append(
            f"[{idx}] severity={item['severity']} confidence={item['confidence']} {item['title']} | evidence={'; '.join(item['evidence'])}"
        )
    return output


def _fix_plan(*, root_causes: list[dict[str, Any]]) -> list[str]:
    base = [
        "Enforce target poisoning for targeted attacks (targeted_promotion and prompt_injection) even when poison_fraction rounds to zero.",
        "Emit field-level poisoning diagnostics and fail-safe warnings when attack changes are marker-only.",
        "Persist retrieval query body, candidate IDs/scores, and target presence in debug traces.",
        "Add evaluation warnings for zero-hit floor and ASR applicability mismatches.",
    ]
    if not root_causes:
        base.append("No critical root causes detected in current run; verify with a new controlled run.")
    return base


def _logging_plan() -> list[str]:
    return [
        "common/schemas/attack_config.py: log config load/normalization (attack_type, poison_fraction, target_movie_id).",
        "agent/datasets/poison_builder.py: log poison build start/complete, changed field counts, target poison status, sample modified movie IDs.",
        "agent/attacks/*.py: log selected poison document IDs before/after target enforcement.",
        "api/app/services/indexing_service.py: log index creation target, mapping path, bulk path, expected docs, poison docs, indexed docs.",
        "rag/recsys/candidate_gen.py: log full Elasticsearch query body plus returned candidate IDs/scores and poison-marker coverage.",
        "api/app/services/recs_service.py: log mode/index/query and ranking input/output IDs, rerank fallback state.",
        "api/app/eval/runner.py: log per-user metric inputs/outputs, overlap, target ranks, ASR reason, artifact output paths.",
    ]


def _validation_checklist() -> list[str]:
    return [
        "Rebuild poisoned bulk and confirm target_movie_id poison state in generated JSONL and movies_poisoned index.",
        "Confirm attacked mode resolves to movies_poisoned and baseline to movies for the same user/query.",
        "Compare baseline vs attacked candidate IDs/scores; verify expected divergence (or explicitly explain lack of divergence).",
        "Verify target presence/rank in retrieval pool and final top-K when running targeted attacks.",
        "Re-run eval and confirm metrics/traces now show explainable behavior changes.",
        "Inspect logs to identify exactly where attack effect is introduced or lost.",
    ]


def _audit_report_markdown(
    *,
    ctx: _RunContext,
    attack_config: AttackConfig,
    llm_ranking_mode: str,
    user_id: int,
    bulk_diff: dict[str, Any],
    retrieval_diff: dict[str, Any],
    metrics_diagnosis: dict[str, Any],
    root_causes: list[dict[str, Any]],
) -> str:
    lines: list[str] = []
    lines.append(f"# Audit Report: {ctx.label}")
    lines.append("")
    lines.append("## Scope")
    lines.append(
        f"- run_dir: `{ctx.run_dir}`\n- attack_type: `{attack_config.attack_type}`\n- ranking_mode: `{llm_ranking_mode}`\n- audited_user_id: `{user_id}`"
    )
    lines.append("")
    lines.append("## Bulk Differential")
    lines.append(
        f"- changed_title: `{bulk_diff.get('changed_title')}`\n- changed_genres: `{bulk_diff.get('changed_genres')}`\n"
        f"- changed_synopsis: `{bulk_diff.get('changed_synopsis')}`\n- changed_any_nonpoison_fields: `{bulk_diff.get('changed_any_nonpoison_fields')}`\n"
        f"- changed_only_poison_fields: `{bulk_diff.get('changed_only_poison_fields')}`\n- target_is_poisoned: `{bulk_diff.get('target_is_poisoned')}`"
    )
    lines.append("")
    lines.append("## Retrieval Differential")
    lines.append(
        f"- candidate_ids_equal: `{retrieval_diff.get('candidate_ids_equal')}`\n"
        f"- candidate_scores_equal: `{retrieval_diff.get('candidate_scores_equal')}`\n"
        f"- candidate_set_jaccard: `{retrieval_diff.get('candidate_set_jaccard')}`"
    )
    lines.append("")
    lines.append("## Metric Diagnosis")
    lines.append(
        f"- baseline: `{metrics_diagnosis.get('summary_baseline')}`\n"
        f"- attacked: `{metrics_diagnosis.get('summary_attacked')}`\n"
        f"- delta: `{metrics_diagnosis.get('summary_delta')}`\n"
        f"- asr_applicable: `{metrics_diagnosis.get('asr_applicable')}`\n"
        f"- asr_reason: `{metrics_diagnosis.get('asr_reason')}`"
    )
    lines.append("")
    lines.append("## Root Causes")
    if not root_causes:
        lines.append("- No high-confidence root cause detected.")
    else:
        for item in root_causes:
            lines.append(
                f"- severity={item['severity']} confidence={item['confidence']} {item['title']} | evidence: {'; '.join(item['evidence'])}"
            )
    lines.append("")
    return "\n".join(lines) + "\n"


def _to_markdown_list(title: str, rows: list[str]) -> str:
    lines = [f"# {title}", ""]
    if not rows:
        lines.append("- none")
    else:
        for row in rows:
            lines.append(f"- {row}")
    lines.append("")
    return "\n".join(lines)


def _to_markdown_numbered(title: str, rows: list[str]) -> str:
    lines = [f"# {title}", ""]
    if not rows:
        lines.append("1. none")
    else:
        for idx, row in enumerate(rows, start=1):
            lines.append(f"{idx}. {row}")
    lines.append("")
    return "\n".join(lines)


def _write_text(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload

