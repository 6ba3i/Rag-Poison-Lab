from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from api.app.cli.commands_data import prepare_data
from api.app.cli.commands_eval import evaluate_run
from api.app.cli.commands_index import index_both
from api.app.cli.commands_report import generate_report_artifacts
from api.app.settings import Settings, build_es_client, get_settings

RunProfile = Literal["pipeline", "single_demo"]


@dataclass(frozen=True)
class ExperimentRunOptions:
    label: str | None
    mode: str
    k: int
    user_id: int | None
    batch_size: int
    run_profile: RunProfile
    run_prepare: bool | None
    run_index: bool | None
    run_eval: bool | None
    run_report: bool | None
    overwrite: bool
    dataset_dir: Path | None
    output_dir: Path | None
    es_url: str | None
    attack_config: Path | None
    repeat_count: int
    seed: int


class ExperimentOrchestrator:
    def run(self, *, options: ExperimentRunOptions) -> dict[str, Any]:
        resolved_options = plan_experiment_run(options=options)
        eval_settings = _resolve_eval_settings(options=resolved_options)
        eval_es_client = _resolve_eval_es_client(options=resolved_options, settings=eval_settings)
        effective_label = resolved_options.label
        result: dict[str, Any] = {
            "label": effective_label,
            "prepare": None,
            "index": None,
            "eval": None,
            "report": None,
            "run_dir": None,
        }

        if resolved_options.run_prepare:
            result["prepare"] = prepare_data(
                dataset_dir=resolved_options.dataset_dir,
                output_dir=resolved_options.output_dir,
                test_holdout=10,
                top_genres_k=5,
                top_rated_k=10,
                recent_k=10,
            )

        if resolved_options.run_index:
            result["index"] = index_both(
                es_url=resolved_options.es_url,
                processed_dir=resolved_options.output_dir,
                attack_config=resolved_options.attack_config,
                build_poisoned_if_missing=False,
            )

        if resolved_options.run_eval:
            eval_summary = evaluate_run(
                mode=resolved_options.mode,  # type: ignore[arg-type]
                label=effective_label,
                k=resolved_options.k,
                user_id=resolved_options.user_id,
                batch_size=resolved_options.batch_size,
                settings=eval_settings,
                es_client=eval_es_client,
                results_root=None,
                overwrite=resolved_options.overwrite,
                attack_config=resolved_options.attack_config,
                repeat_count=resolved_options.repeat_count,
                seed=resolved_options.seed,
            )
            result["eval"] = eval_summary
            effective_label = str(eval_summary.get("label") or effective_label)
            result["label"] = effective_label
            result["run_dir"] = str(eval_summary.get("run_dir")) if eval_summary.get("run_dir") is not None else None

        if resolved_options.run_report:
            report_summary = generate_report_artifacts(
                label=effective_label,
                run_dir=None,
                results_root=None,
            )
            result["report"] = report_summary
            if result["run_dir"] is None:
                result["run_dir"] = str(report_summary.get("run_dir"))

        return result


def plan_experiment_run(*, options: ExperimentRunOptions) -> ExperimentRunOptions:
    if options.mode not in {"single", "batch", "full"}:
        raise ValueError(f"Unsupported experiment mode: {options.mode}")
    if options.run_profile not in {"pipeline", "single_demo"}:
        raise ValueError(f"Unsupported run_profile: {options.run_profile}")
    if options.run_profile == "single_demo" and options.mode != "single":
        raise ValueError("run_profile=single_demo requires mode=single")

    defaults = _profile_stage_defaults(run_profile=options.run_profile)
    resolved_batch_size = 1 if options.mode == "single" else int(options.batch_size)

    return ExperimentRunOptions(
        label=options.label,
        mode=options.mode,
        k=options.k,
        user_id=options.user_id,
        batch_size=resolved_batch_size,
        run_profile=options.run_profile,
        run_prepare=options.run_prepare if options.run_prepare is not None else defaults["run_prepare"],
        run_index=options.run_index if options.run_index is not None else defaults["run_index"],
        run_eval=options.run_eval if options.run_eval is not None else defaults["run_eval"],
        run_report=options.run_report if options.run_report is not None else defaults["run_report"],
        overwrite=options.overwrite,
        dataset_dir=options.dataset_dir,
        output_dir=options.output_dir,
        es_url=options.es_url,
        attack_config=options.attack_config,
        repeat_count=options.repeat_count,
        seed=options.seed,
    )


def _profile_stage_defaults(*, run_profile: RunProfile) -> dict[str, bool]:
    if run_profile == "single_demo":
        return {
            "run_prepare": False,
            "run_index": False,
            "run_eval": True,
            "run_report": False,
        }
    return {
        "run_prepare": True,
        "run_index": True,
        "run_eval": True,
        "run_report": True,
    }


def resolve_optional_path(value: str | None) -> Path | None:
    if value is None:
        return None
    return Path(value).resolve()


def _resolve_eval_settings(*, options: ExperimentRunOptions) -> Settings | None:
    if options.output_dir is None:
        return None
    base_settings = get_settings()
    payload = base_settings.model_dump()
    payload["processed_root"] = options.output_dir
    return Settings.model_validate(payload)


def _resolve_eval_es_client(*, options: ExperimentRunOptions, settings: Settings | None) -> Any | None:
    if options.es_url is None:
        return None
    return build_es_client(es_url=options.es_url, settings=settings)
