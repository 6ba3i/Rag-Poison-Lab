from __future__ import annotations

import json
import os
import random
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import pandas as pd
import questionary
import typer
from questionary import Choice

from api.app.cli.commands_attack import build_poisoned
from api.app.cli.commands_data import build_es_bulk, build_profiles, build_splits, prepare_data
from api.app.cli.commands_eval import evaluate_run
from api.app.cli.commands_index import index_baseline, index_both, index_poisoned, index_reset, index_stats
from api.app.cli.commands_report import generate_report_artifacts
from api.app.data.paths import ES_BULK_POISONED_MOVIES_JSONL, MOVIES_PARQUET, resolve_default_dataset_dir, resolve_default_processed_dir
from api.app.eval.reporting import list_run_labels
from api.app.llm.credentials import resolve_api_key
from api.app.llm.registry import LlmRegistry
from api.app.services.indexing_service import preflight_es
from api.app.settings import Settings, get_settings
from common.schemas.attack_config import AttackConfig, default_attack_config, load_attack_config
from common.schemas.llm_config import LlmConfig, LlmRoleConfig, RankingMode, default_llm_config

TARGET_POOL_SIZE = 20
TARGET_PICK_SEED = 42
RESET_CONFIRMATION_TEXT = "RESET"


def run_wizard() -> None:
    typer.echo("RAGPoison Full Workflow Wizard")

    while True:
        choice = _select(
            "Main menu",
            choices=[
                Choice("1) Environment checks", "env"),
                Choice("2) Configure LLMs", "llm"),
                Choice("3) Data pipeline", "data"),
                Choice("4) Elasticsearch indexing", "index"),
                Choice("5) Configure attack", "attack"),
                Choice("6) Run experiments", "eval"),
                Choice("7) Generate reports", "report"),
                Choice("8) Utilities", "utils"),
                Choice("9) Exit", "exit"),
            ],
        )

        if choice in {None, "exit"}:
            typer.echo("Wizard exited")
            return

        try:
            if choice == "env":
                _environment_checks_screen()
            elif choice == "llm":
                _configure_llms_screen()
            elif choice == "data":
                _data_pipeline_screen()
            elif choice == "index":
                _indexing_screen()
            elif choice == "attack":
                _configure_attack_screen()
            elif choice == "eval":
                _run_experiments_screen()
            elif choice == "report":
                _generate_reports_screen()
            elif choice == "utils":
                _utilities_screen()
        except Exception as exc:  # noqa: BLE001
            typer.echo(f"Screen failed: {exc}")


def _environment_checks_screen() -> None:
    settings = get_settings()
    registry = LlmRegistry(settings=settings)

    dataset_dir = resolve_default_dataset_dir()
    data_root = settings.resolved_data_root
    kibana_url = _kibana_url()

    checks: list[dict[str, str]] = []
    checks.append(
        _check_path_exists(
            "Dataset directory exists",
            dataset_dir,
            fix=_path_fix_hint(path=dataset_dir, host_fix="Ensure ./ml-100 exists in the repo root."),
        )
    )
    checks.append(
        _check_writable_dir(
            "Data directory writable",
            data_root,
            fix=_path_fix_hint(path=data_root, host_fix="Ensure ./data exists and is writable in the repo root."),
        )
    )
    checks.append(
        _check_http(
            "Elasticsearch reachable",
            f"{settings.elasticsearch_url.rstrip('/')}/_cluster/health",
            fix="Start Elasticsearch and verify ELASTICSEARCH_URL",
        )
    )
    checks.append(
        _check_http(
            "Kibana reachable (optional)",
            f"{kibana_url.rstrip('/')}/api/status",
            fix=f"Optional: start Kibana and open {kibana_url} (host fallback: http://localhost:5601)",
            optional=True,
        )
    )

    ollama_ok = registry.ollama_connectivity()
    checks.append(
        {
            "name": "Ollama reachable",
            "status": "PASS" if ollama_ok else "FAIL",
            "detail": settings.ollama_base_url,
            "fix": "Start Ollama service and verify OLLAMA_BASE_URL",
        }
    )

    provider_env_key = {
        "chatgpt": "CHATGPT_API_KEY",
        "claude": "CLAUDE_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "qwen": "QWEN_API_KEY",
    }
    for provider, secret_path in settings.provider_secret_paths.items():
        api_key, source = resolve_api_key(provider_name=provider, settings=settings, warn_on_file_fallback=False)
        exists = api_key is not None
        if source.startswith("file:"):
            detail = f"{source} ({secret_path}) [deprecated fallback]"
        elif source.startswith("env:"):
            detail = source
        else:
            detail = "missing"
        env_name = provider_env_key.get(provider, "API_KEY")
        checks.append(
            {
                "name": f"Secret present: {provider}",
                "status": "PASS" if exists else "WARN",
                "detail": detail,
                "fix": f"Set {env_name} in .env/.env.key (legacy fallback: {secret_path})",
            }
        )

    typer.echo("\nEnvironment checks")
    for item in checks:
        typer.echo(f"[{item['status']}] {item['name']}: {item['detail']}")
        if item["status"] in {"FAIL", "WARN"}:
            typer.echo(f"  Fix: {item['fix']}")

    typer.echo("")
    _wait_for_enter()


def _configure_llms_screen() -> None:
    settings = get_settings()
    registry = LlmRegistry(settings=settings)

    while True:
        current = _load_llm_config(settings)
        choice = _select(
            "Configure LLMs",
            choices=[
                Choice("Edit victim + attacker", "edit"),
                Choice("Show current config", "show"),
                Choice("Back", "back"),
            ],
        )

        if choice in {None, "back"}:
            return

        if choice == "show":
            typer.echo(json.dumps(current.model_dump(), indent=2, sort_keys=True))
            _wait_for_enter()
            continue

        updated = _prompt_role_config(registry=registry, role_name="victim", current=current.victim)
        if updated is None:
            continue
        victim = updated

        updated = _prompt_role_config(registry=registry, role_name="attacker", current=current.attacker)
        if updated is None:
            continue
        attacker = updated

        ranking_mode = _prompt_ranking_mode(default=current.ranking_mode)
        if ranking_mode is None:
            continue

        new_config = LlmConfig(victim=victim, attacker=attacker, ranking_mode=ranking_mode)
        _save_llm_config(settings=settings, config=new_config)
        typer.echo(f"Saved {settings.resolved_llm_config_path}")

        if _confirm("Run optional test call for both roles?", default=False):
            _test_llm_roles(registry=registry, config=new_config)

        _wait_for_enter()


def _data_pipeline_screen() -> None:
    while True:
        choice = _select(
            "Data pipeline",
            choices=[
                Choice("preprocess", "prepare"),
                Choice("profiles", "profiles"),
                Choice("splits", "splits"),
                Choice("export baseline bulk", "export"),
                Choice("run all", "all"),
                Choice("Back", "back"),
            ],
        )

        if choice in {None, "back"}:
            return

        dataset_dir = _prompt_path("Dataset directory", resolve_default_dataset_dir())
        output_dir = _prompt_path("Output directory", resolve_default_processed_dir())

        if choice in {"prepare", "all"}:
            summary = prepare_data(
                dataset_dir=dataset_dir,
                output_dir=output_dir,
                test_holdout=_prompt_int("Test holdout (last N ratings per user)", 10, minimum=1),
                top_genres_k=_prompt_int("Top genres per user", 5, minimum=1),
                top_rated_k=_prompt_int("Top rated movie IDs per user", 10, minimum=1),
                recent_k=_prompt_int("Recent movie IDs per user", 10, minimum=1),
            )
        elif choice == "profiles":
            summary = build_profiles(
                dataset_dir=dataset_dir,
                output_dir=output_dir,
                top_genres_k=_prompt_int("Top genres per user", 5, minimum=1),
                top_rated_k=_prompt_int("Top rated movie IDs per user", 10, minimum=1),
                recent_k=_prompt_int("Recent movie IDs per user", 10, minimum=1),
            )
        elif choice == "splits":
            summary = build_splits(
                dataset_dir=dataset_dir,
                output_dir=output_dir,
                test_holdout=_prompt_int("Test holdout (last N ratings per user)", 10, minimum=1),
            )
        else:
            summary = build_es_bulk(dataset_dir=dataset_dir, output_dir=output_dir)

        _print_summary(summary)
        _wait_for_enter()


def _indexing_screen() -> None:
    settings = get_settings()

    while True:
        choice = _select(
            "Elasticsearch indexing",
            choices=[
                Choice("index baseline", "baseline"),
                Choice("index poisoned", "poisoned"),
                Choice("index both", "both"),
                Choice("Back", "back"),
            ],
        )

        if choice in {None, "back"}:
            return

        es_url = _prompt_text("Elasticsearch URL", settings.elasticsearch_url)
        try:
            banner = preflight_es(es_url=es_url)
            version = banner.get("version") or "unknown"
            name = banner.get("name") or "unknown"
            typer.echo(f"Elasticsearch preflight OK: {name} (version: {version})")
        except Exception as exc:  # noqa: BLE001
            typer.echo(f"Elasticsearch preflight failed: {exc}")
            _wait_for_enter()
            continue

        processed_dir = _prompt_path("Processed directory", resolve_default_processed_dir())

        if choice == "baseline":
            summary = index_baseline(es_url=es_url, processed_dir=processed_dir)
        elif choice == "poisoned":
            _ensure_poisoned_bulk(processed_dir=processed_dir)
            summary = index_poisoned(es_url=es_url, processed_dir=processed_dir)
        else:
            _ensure_poisoned_bulk(processed_dir=processed_dir)
            summary = index_both(es_url=es_url, processed_dir=processed_dir)

        _print_summary(summary)
        typer.echo("Index stats:")
        _print_summary(index_stats(es_url=es_url), prefix="  ")
        _wait_for_enter()


def _configure_attack_screen() -> None:
    settings = get_settings()
    config_path = (settings.resolved_config_dir / "attack_config.json").resolve()

    while True:
        current = _load_attack_config(config_path)
        choice = _select(
            "Configure attack",
            choices=[
                Choice("Edit attack config", "edit"),
                Choice("Show current config", "show"),
                Choice("Back", "back"),
            ],
        )

        if choice in {None, "back"}:
            return

        if choice == "show":
            typer.echo(json.dumps(current.model_dump(), indent=2, sort_keys=True))
            _wait_for_enter()
            continue

        attack_type = _select(
            "Attack type",
            choices=[
                Choice("targeted_promotion", "targeted_promotion"),
                Choice("untargeted_degradation", "untargeted_degradation"),
                Choice("prompt_injection", "prompt_injection"),
                Choice("Back", "back"),
            ],
            default=current.attack_type,
        )
        if attack_type in {None, "back"}:
            continue

        poison_fraction = _prompt_float("Poison fraction (0.0-1.0)", current.poison_fraction, minimum=0.0, maximum=1.0)

        target_mode = _select(
            "Target movie selection",
            choices=[
                Choice("manual", "manual"),
                Choice("random head", "random_head"),
                Choice("random tail", "random_tail"),
                Choice("none", "none"),
                Choice("Back", "back"),
            ],
            default="manual" if current.target_movie_id is not None else "none",
        )
        if target_mode in {None, "back"}:
            continue

        target_movie_id: int | None
        if target_mode == "manual":
            target_movie_id = _prompt_int(
                "Target movie ID",
                current.target_movie_id if current.target_movie_id is not None else 1,
                minimum=1,
            )
        elif target_mode == "random_head":
            target_movie_id = _pick_target_movie_id(mode="head", processed_dir=settings.resolved_processed_dir)
            typer.echo(f"Selected target_movie_id={target_movie_id} (deterministic seed={TARGET_PICK_SEED})")
        elif target_mode == "random_tail":
            target_movie_id = _pick_target_movie_id(mode="tail", processed_dir=settings.resolved_processed_dir)
            typer.echo(f"Selected target_movie_id={target_movie_id} (deterministic seed={TARGET_PICK_SEED})")
        else:
            target_movie_id = None

        payload_text = _prompt_text(
            "Payload text",
            current.payload_text if current.payload_text.strip() else default_attack_config().payload_text,
        )

        keyword_text = _prompt_text(
            "Keyword list (comma-separated)",
            ", ".join(current.keyword_list) if current.keyword_list else ", ".join(default_attack_config().keyword_list),
        )
        keyword_list = [item.strip() for item in keyword_text.split(",") if item.strip()]

        target_boost_policy = current.target_boost_policy
        target_boost_strength = current.target_boost_strength
        target_fields = list(current.target_fields)
        if attack_type == "targeted_promotion":
            boost_policy = _select(
                "Target boost policy",
                choices=[
                    Choice("keyword_burst", "keyword_burst"),
                    Choice("aggressive", "aggressive"),
                    Choice("disabled", "disabled"),
                    Choice("Back", "back"),
                ],
                default=current.target_boost_policy,
            )
            if boost_policy in {None, "back"}:
                continue
            target_boost_policy = str(boost_policy)
            target_boost_strength = _prompt_int(
                "Target boost strength (1-20)",
                current.target_boost_strength,
                minimum=1,
                maximum=20,
            )
            target_fields_text = _prompt_text(
                "Target boost fields (comma-separated: title,genres,synopsis)",
                ", ".join(current.target_fields),
            )
            parsed_fields = [item.strip().lower() for item in target_fields_text.split(",") if item.strip()]
            if parsed_fields:
                target_fields = parsed_fields

        config = AttackConfig(
            attack_type=attack_type,
            poison_fraction=poison_fraction,
            target_movie_id=target_movie_id,
            payload_text=payload_text,
            keyword_list=keyword_list,
            target_boost_policy=target_boost_policy,
            target_boost_strength=target_boost_strength,
            target_fields=target_fields,
        )

        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(config.model_dump(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        typer.echo(f"Saved {config_path}")
        _wait_for_enter()


def _run_experiments_screen() -> None:
    while True:
        choice = _select(
            "Run experiments",
            choices=[
                Choice("single user demo", "single"),
                Choice("batch N users", "batch"),
                Choice("full dataset", "full"),
                Choice("Back", "back"),
            ],
        )

        if choice in {None, "back"}:
            return

        label_default = datetime.now(timezone.utc).strftime("run_%Y%m%d_%H%M%S")
        label = _prompt_text("Run label", label_default)
        k = _prompt_int("K for metrics", 10, minimum=1)

        if choice == "single":
            user_id_text = _prompt_text("User ID (leave blank for auto viable selection)", "")
            user_id_value: int | None
            if user_id_text.strip() == "":
                user_id_value = None
            else:
                try:
                    user_id_value = int(user_id_text)
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"Invalid user ID: {user_id_text}") from exc
                if user_id_value <= 0:
                    raise ValueError("User ID must be >= 1")
            summary = evaluate_run(
                mode="single",
                label=label,
                k=k,
                user_id=user_id_value,
                batch_size=1,
                results_root=None,
            )
        elif choice == "batch":
            batch_size = _prompt_int("Batch size (N users)", 100, minimum=1)
            summary = evaluate_run(
                mode="batch",
                label=label,
                k=k,
                user_id=None,
                batch_size=batch_size,
                results_root=None,
            )
        else:
            summary = evaluate_run(
                mode="full",
                label=label,
                k=k,
                user_id=None,
                batch_size=1,
                results_root=None,
            )

        _print_summary(summary)
        _wait_for_enter()


def _generate_reports_screen() -> None:
    while True:
        labels = list_run_labels()
        choices: list[Choice] = [Choice(label, label) for label in labels]
        choices.extend([Choice("Custom label", "custom"), Choice("Back", "back")])

        choice = _select("Generate reports", choices=choices)
        if choice in {None, "back"}:
            return

        if choice == "custom":
            label = _prompt_text("Run label", "")
            if label.strip() == "":
                typer.echo("Run label cannot be empty")
                continue
        else:
            label = str(choice)

        summary = generate_report_artifacts(label=label, run_dir=None, results_root=None)
        _print_summary(summary)
        _wait_for_enter()


def _utilities_screen() -> None:
    settings = get_settings()

    while True:
        choice = _select(
            "Utilities",
            choices=[
                Choice("show current config", "show_config"),
                Choice("reset indices", "reset_indices"),
                Choice("show Kibana URL", "kibana"),
                Choice("show ES doc counts", "doc_counts"),
                Choice("Back", "back"),
            ],
        )

        if choice in {None, "back"}:
            return

        if choice == "show_config":
            llm_config = _load_llm_config(settings)
            attack_config = _load_attack_config((settings.resolved_config_dir / "attack_config.json").resolve())
            typer.echo("LLM config:")
            typer.echo(json.dumps(llm_config.model_dump(), indent=2, sort_keys=True))
            typer.echo("Attack config:")
            typer.echo(json.dumps(attack_config.model_dump(), indent=2, sort_keys=True))
            _wait_for_enter()
            continue

        if choice == "reset_indices":
            typed = _prompt_text(
                f"Type {RESET_CONFIRMATION_TEXT} to confirm deleting movies and movies_poisoned",
                "",
            )
            if typed.strip() != RESET_CONFIRMATION_TEXT:
                typer.echo("Reset cancelled")
            else:
                summary = index_reset(es_url=settings.elasticsearch_url)
                _print_summary(summary)
            _wait_for_enter()
            continue

        if choice == "kibana":
            url = _kibana_url()
            typer.echo(f"Kibana internal URL: {url}")
            typer.echo("Kibana host URL: http://localhost:5601")
            _wait_for_enter()
            continue

        if choice == "doc_counts":
            summary = index_stats(es_url=settings.elasticsearch_url)
            _print_summary(summary)
            _wait_for_enter()


def _check_path_exists(name: str, path: Path, *, fix: str) -> dict[str, str]:
    exists = path.exists() and path.is_dir()
    return {
        "name": name,
        "status": "PASS" if exists else "FAIL",
        "detail": str(path),
        "fix": fix,
    }


def _check_writable_dir(name: str, path: Path, *, fix: str) -> dict[str, str]:
    if not path.exists() or not path.is_dir():
        return {
            "name": name,
            "status": "FAIL",
            "detail": str(path),
            "fix": fix,
        }

    probe = path / ".wizard_write_probe"
    try:
        probe.write_text("ok\n", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except Exception:  # noqa: BLE001
        return {
            "name": name,
            "status": "FAIL",
            "detail": str(path),
            "fix": fix,
        }

    return {
        "name": name,
        "status": "PASS",
        "detail": str(path),
        "fix": fix,
    }


def _check_http(name: str, url: str, *, fix: str, optional: bool = False) -> dict[str, str]:
    ok = _http_get_ok(url)
    status = "PASS" if ok else ("WARN" if optional else "FAIL")
    return {
        "name": name,
        "status": status,
        "detail": url,
        "fix": fix,
    }


def _http_get_ok(url: str, timeout: int = 3) -> bool:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return 200 <= response.status < 400
    except urllib.error.HTTPError as exc:
        return 200 <= exc.code < 400
    except Exception:  # noqa: BLE001
        return False


def _path_fix_hint(*, path: Path, host_fix: str) -> str:
    resolved = path.resolve()
    if resolved == Path("/workspace") or Path("/workspace") in resolved.parents:
        return f"Bind-mount ./{path.name} to {resolved}"
    return host_fix


def _load_llm_config(settings: Settings) -> LlmConfig:
    path = settings.resolved_llm_config_path
    if not path.exists() or path.stat().st_size == 0:
        config = default_llm_config()
        _save_llm_config(settings=settings, config=config)
        return config

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return LlmConfig.model_validate(payload)
    except Exception:  # noqa: BLE001
        config = default_llm_config()
        _save_llm_config(settings=settings, config=config)
        return config


def _save_llm_config(*, settings: Settings, config: LlmConfig) -> None:
    path = settings.resolved_llm_config_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config.model_dump(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _prompt_role_config(*, registry: LlmRegistry, role_name: str, current: LlmRoleConfig) -> LlmRoleConfig | None:
    options = {item.provider: item for item in registry.list_provider_options()}

    provider_choices: list[Choice] = []
    for provider in ["local", "chatgpt", "claude", "gemini", "qwen"]:
        option = options.get(provider)
        if option is None:
            continue

        label = provider
        if provider != "local" and not option.available:
            provider_choices.append(Choice(title=f"{label} (secret missing)", value=provider, disabled="secret missing"))
        else:
            provider_choices.append(Choice(title=label, value=provider))

    provider_choices.append(Choice("Back", "back"))

    provider = _select(
        f"Select provider for {role_name}",
        choices=provider_choices,
        default=current.provider,
    )
    if provider in {None, "back"}:
        return None

    provider_key = str(provider)
    option = options.get(provider_key)
    models = option.models if option is not None else []

    if models:
        model_choice = _select(
            f"Select model for {role_name} ({provider_key})",
            choices=[*models, Choice("Custom model", "custom"), Choice("Back", "back")],
            default=current.model if current.model in models else None,
        )
        if model_choice in {None, "back"}:
            return None
        if model_choice == "custom":
            model = _prompt_text(f"Custom model for {role_name}", current.model)
        else:
            model = str(model_choice)
    else:
        model = _prompt_text(f"Model for {role_name} ({provider_key})", current.model)

    return LlmRoleConfig(provider=provider_key, model=model)


def _prompt_ranking_mode(*, default: RankingMode) -> RankingMode | None:
    choice = _select(
        "Select ranking mode",
        choices=[
            Choice("Deterministic (BM25 + genre overlap)", "deterministic"),
            Choice("LLM rerank (experimental — vulnerable to prompt injection)", "llm_rerank"),
            Choice("Back", "back"),
        ],
        default=default,
    )
    if choice in {None, "back"}:
        return None
    selected = str(choice)
    if selected not in {"deterministic", "llm_rerank"}:
        return None
    return cast(RankingMode, selected)


def _test_llm_roles(*, registry: LlmRegistry, config: LlmConfig) -> None:
    for role_name, role in (("victim", config.victim), ("attacker", config.attacker)):
        try:
            client = registry.get_provider_client(provider=role.provider, model=role.model)
            response = client.generate(
                prompt="Reply with exactly one word: OK",
                system="You are a test assistant.",
                temperature=0.0,
                max_tokens=16,
            )
            typer.echo(f"{role_name}: PASS ({response.strip()[:120]})")
        except Exception as exc:  # noqa: BLE001
            typer.echo(f"{role_name}: FAIL ({exc})")


def _load_attack_config(path: Path) -> AttackConfig:
    if not path.exists() or path.stat().st_size == 0:
        config = default_attack_config()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config.model_dump(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return config
    return load_attack_config(path)


def _pick_target_movie_id(*, mode: str, processed_dir: Path) -> int:
    movie_ids = _load_movie_ids(processed_dir)
    if not movie_ids:
        raise RuntimeError(
            f"No movie IDs found in {processed_dir / MOVIES_PARQUET}; run data pipeline preprocess first"
        )

    sorted_ids = sorted(movie_ids)
    if mode == "head":
        pool = sorted_ids[:TARGET_POOL_SIZE]
    else:
        pool = sorted_ids[-TARGET_POOL_SIZE:]

    if not pool:
        raise RuntimeError("Unable to pick target movie from empty pool")

    return int(random.Random(TARGET_PICK_SEED).choice(pool))


def _load_movie_ids(processed_dir: Path) -> list[int]:
    movies_path = processed_dir / MOVIES_PARQUET
    if not movies_path.exists() or movies_path.stat().st_size == 0:
        return []

    df = pd.read_parquet(movies_path)
    if "movie_id" not in df.columns:
        return []

    ids: list[int] = []
    for raw in df["movie_id"].tolist():
        try:
            ids.append(int(raw))
        except Exception:  # noqa: BLE001
            continue
    return ids


def _ensure_poisoned_bulk(*, processed_dir: Path) -> None:
    poisoned_path = processed_dir / ES_BULK_POISONED_MOVIES_JSONL
    if poisoned_path.exists() and poisoned_path.stat().st_size > 0:
        return

    if not _confirm(
        f"{poisoned_path} is missing. Build poisoned bulk now?",
        default=True,
    ):
        raise RuntimeError("Poisoned bulk is required for poisoned indexing")

    summary = build_poisoned(processed_dir=processed_dir, attack_config=None)
    _print_summary(summary)


def _kibana_url() -> str:
    return os.environ.get("KIBANA_URL", "http://kibana:5601").strip() or "http://kibana:5601"


def _select(message: str, *, choices: list[Any], default: str | None = None) -> Any:
    return questionary.select(message, choices=choices, default=default).ask()


def _confirm(message: str, *, default: bool = True) -> bool:
    answer = questionary.confirm(message, default=default).ask()
    return bool(answer)


def _prompt_text(message: str, default: str) -> str:
    raw = questionary.text(message, default=default).ask()
    if raw is None:
        return default
    value = str(raw).strip()
    return value if value else default


def _prompt_path(message: str, default_path: Path) -> Path:
    raw = questionary.text(message, default=str(default_path)).ask()
    if raw is None:
        return default_path.resolve()
    value = str(raw).strip()
    return Path(value or str(default_path)).resolve()


def _prompt_int(message: str, default: int, minimum: int = 1) -> int:
    raw = questionary.text(message, default=str(default)).ask()
    value = int(raw) if raw is not None and str(raw).strip() != "" else default
    if value < minimum:
        raise ValueError(f"Value must be >= {minimum}")
    return value


def _prompt_float(message: str, default: float, minimum: float, maximum: float) -> float:
    raw = questionary.text(message, default=str(default)).ask()
    value = float(raw) if raw is not None and str(raw).strip() != "" else float(default)
    if value < minimum or value > maximum:
        raise ValueError(f"Value must be between {minimum} and {maximum}")
    return value


def _print_summary(summary: dict[str, Any], *, prefix: str = "") -> None:
    for key, value in summary.items():
        if isinstance(value, dict):
            typer.echo(f"{prefix}{key}:")
            _print_summary(value, prefix=prefix + "  ")
            continue
        typer.echo(f"{prefix}{key}: {value}")


def _wait_for_enter() -> None:
    questionary.text("Press Enter to continue", default="").ask()
