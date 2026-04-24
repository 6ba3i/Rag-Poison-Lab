from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import threading

from api.app.cli.commands_attack import build_poisoned
from api.app.cli.commands_index import index_baseline, index_poisoned
from api.app.settings import Settings

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class _ReindexState:
    running: bool = False
    rerun_requested: bool = False
    trigger_count: int = 0
    run_count: int = 0
    last_reason: str | None = None
    last_started_at_utc: str | None = None
    last_finished_at_utc: str | None = None
    last_error: str | None = None


@dataclass(frozen=True)
class ConfigReindexTrigger:
    started: bool
    queued: bool
    running: bool
    reason: str
    es_url: str
    enabled: bool


_STATE = _ReindexState()
_STATE_LOCK = threading.Lock()
_WORKER: threading.Thread | None = None


def trigger_config_reindex(*, settings: Settings, reason: str) -> ConfigReindexTrigger:
    es_url = settings.auto_reindex_es_url
    if not settings.auto_reindex_on_config_change:
        logger.info(
            "config_reindex_skip reason=%s enabled=false es_url=%s",
            reason,
            es_url,
        )
        return ConfigReindexTrigger(
            started=False,
            queued=False,
            running=False,
            reason=reason,
            es_url=es_url,
            enabled=False,
        )

    with _STATE_LOCK:
        _STATE.trigger_count += 1
        _STATE.last_reason = reason
        if _STATE.running:
            _STATE.rerun_requested = True
            logger.info(
                "config_reindex_trigger reason=%s started=false queued=true running=true trigger_count=%s run_count=%s",
                reason,
                _STATE.trigger_count,
                _STATE.run_count,
            )
            return ConfigReindexTrigger(
                started=False,
                queued=True,
                running=True,
                reason=reason,
                es_url=es_url,
                enabled=True,
            )

        _STATE.running = True
        _STATE.rerun_requested = False
        _STATE.last_started_at_utc = _utc_now_iso()
        _STATE.last_error = None

        global _WORKER
        _WORKER = threading.Thread(
            target=_run_worker_loop,
            kwargs={
                "settings": settings,
            },
            daemon=True,
            name="config-reindex-worker",
        )
        _WORKER.start()

        logger.info(
            "config_reindex_trigger reason=%s started=true queued=false running=true trigger_count=%s run_count=%s",
            reason,
            _STATE.trigger_count,
            _STATE.run_count,
        )
        return ConfigReindexTrigger(
            started=True,
            queued=False,
            running=True,
            reason=reason,
            es_url=es_url,
            enabled=True,
        )


def _run_worker_loop(*, settings: Settings) -> None:
    while True:
        error_text: str | None = None
        try:
            _run_single_pipeline(settings=settings)
        except Exception as exc:  # noqa: BLE001
            error_text = f"{type(exc).__name__}: {exc}"
            logger.exception("config_reindex_pipeline_failed error=%s", error_text)

        with _STATE_LOCK:
            _STATE.run_count += 1
            _STATE.last_finished_at_utc = _utc_now_iso()
            _STATE.last_error = error_text
            if _STATE.rerun_requested:
                _STATE.rerun_requested = False
                _STATE.last_started_at_utc = _utc_now_iso()
                logger.info(
                    "config_reindex_pipeline_rerun reason=%s trigger_count=%s run_count=%s",
                    _STATE.last_reason,
                    _STATE.trigger_count,
                    _STATE.run_count,
                )
                continue
            _STATE.running = False
            logger.info(
                "config_reindex_worker_idle trigger_count=%s run_count=%s last_error=%s",
                _STATE.trigger_count,
                _STATE.run_count,
                _STATE.last_error,
            )
            return


def _run_single_pipeline(*, settings: Settings) -> None:
    es_url = settings.auto_reindex_es_url
    processed_dir = settings.resolved_processed_dir
    attack_config_path = settings.resolved_attack_config_path

    logger.info(
        "config_reindex_pipeline_start es_url=%s processed_dir=%s attack_config_path=%s",
        es_url,
        processed_dir,
        attack_config_path,
    )
    baseline_summary = index_baseline(
        es_url=es_url,
        processed_dir=processed_dir,
    )
    poison_build_summary = build_poisoned(
        processed_dir=processed_dir,
        attack_config=attack_config_path,
    )
    poisoned_summary = index_poisoned(
        es_url=es_url,
        processed_dir=processed_dir,
        attack_config=attack_config_path,
    )
    logger.info(
        "config_reindex_pipeline_complete es_url=%s baseline=%s build_poisoned=%s index_poisoned=%s",
        es_url,
        baseline_summary,
        poison_build_summary,
        poisoned_summary,
    )
