from __future__ import annotations

import json
import logging
import threading
from queue import Empty, Queue
from typing import Any, Iterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from api.app.services.orchestration_service import ExperimentOrchestrator, ExperimentRunOptions, resolve_optional_path
from common.schemas.api_types import ExperimentRunRequest, ExperimentRunResponse

router = APIRouter(tags=["experiments"])
logger = logging.getLogger(__name__)


class _ThreadLogCaptureHandler(logging.Handler):
    def __init__(self, *, event_queue: Queue[bytes | None], target_thread_id: int) -> None:
        super().__init__()
        self._event_queue = event_queue
        self._target_thread_id = target_thread_id

    def emit(self, record: logging.LogRecord) -> None:
        if record.thread != self._target_thread_id:
            return

        try:
            line = self.format(record)
        except Exception:  # noqa: BLE001
            line = record.getMessage()
        self._event_queue.put(_encode_sse(event="log", payload={"line": line}))


@router.post("/experiments/run", response_model=ExperimentRunResponse)
def run_experiment(payload: ExperimentRunRequest) -> ExperimentRunResponse:
    try:
        result = _run_orchestrator(options=_resolve_run_options(payload))
    except Exception as exc:  # noqa: BLE001
        status_code, detail = _map_run_exception(exc)
        raise HTTPException(status_code=status_code, detail=detail) from exc

    return ExperimentRunResponse.model_validate(result)


@router.post("/experiments/run/stream")
def run_experiment_stream(payload: ExperimentRunRequest) -> StreamingResponse:
    options = _resolve_run_options(payload)
    event_queue: Queue[bytes | None] = Queue()
    root_logger = logging.getLogger()

    def _worker() -> None:
        handler = _ThreadLogCaptureHandler(event_queue=event_queue, target_thread_id=threading.get_ident())
        handler.setFormatter(_resolve_log_formatter(root_logger=root_logger))
        root_logger.addHandler(handler)

        try:
            result = _run_orchestrator(options=options)
        except Exception as exc:  # noqa: BLE001
            status_code, detail = _map_run_exception(exc)
            event_queue.put(_encode_sse(event="failed", payload={"status_code": status_code, "detail": detail}))
        else:
            validated = ExperimentRunResponse.model_validate(result)
            event_queue.put(_encode_sse(event="complete", payload={"summary": validated.model_dump(mode="json")}))
        finally:
            try:
                root_logger.removeHandler(handler)
            except Exception as exc:  # noqa: BLE001
                logger.debug("Failed to detach stream log capture handler", exc_info=exc)
            event_queue.put(None)

    worker = threading.Thread(target=_worker, name="experiment-run-stream", daemon=True)
    worker.start()

    def _stream_events() -> Iterator[bytes]:
        while True:
            try:
                item = event_queue.get(timeout=0.2)
            except Empty:
                if not worker.is_alive():
                    break
                continue
            if item is None:
                break
            yield item

    return StreamingResponse(
        _stream_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _resolve_run_options(payload: ExperimentRunRequest) -> ExperimentRunOptions:
    return ExperimentRunOptions(
        label=payload.label,
        mode=payload.mode,
        k=payload.k,
        user_id=payload.user_id,
        batch_size=payload.batch_size,
        run_profile=payload.run_profile,
        run_prepare=payload.run_prepare,
        run_index=payload.run_index,
        run_eval=payload.run_eval,
        run_report=payload.run_report,
        overwrite=payload.overwrite,
        dataset_dir=resolve_optional_path(payload.dataset_dir),
        output_dir=resolve_optional_path(payload.output_dir),
        es_url=payload.es_url,
        attack_config=resolve_optional_path(payload.attack_config),
        repeat_count=payload.repeat_count,
        seed=payload.seed,
    )


def _run_orchestrator(*, options: ExperimentRunOptions) -> dict[str, Any]:
    orchestrator = ExperimentOrchestrator()
    return orchestrator.run(options=options)


def _map_run_exception(exc: Exception) -> tuple[int, str]:
    if isinstance(exc, FileNotFoundError):
        return 404, str(exc)
    if isinstance(exc, ValueError):
        return 400, str(exc)
    if isinstance(exc, RuntimeError):
        return 409, str(exc)
    return 500, str(exc)


def _resolve_log_formatter(*, root_logger: logging.Logger) -> logging.Formatter:
    for handler in root_logger.handlers:
        if handler.formatter is not None:
            return handler.formatter
    return logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")


def _encode_sse(*, event: str, payload: dict[str, Any]) -> bytes:
    body = json.dumps(payload, ensure_ascii=False)
    return f"event: {event}\ndata: {body}\n\n".encode("utf-8")
