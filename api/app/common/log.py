from __future__ import annotations

import logging
import os

DEFAULT_LOG_LEVEL = "INFO"


def configure_logging(*, level: str | None = None) -> None:
    desired = (level or os.environ.get("RAGPOISON_LOG_LEVEL") or DEFAULT_LOG_LEVEL).upper()
    root = logging.getLogger()
    if root.handlers:
        root.setLevel(_safe_level(desired))
        return

    logging.basicConfig(
        level=_safe_level(desired),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def _safe_level(value: str) -> int:
    return getattr(logging, value, logging.INFO)
