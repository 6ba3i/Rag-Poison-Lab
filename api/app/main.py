from __future__ import annotations

import logging
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.app.common.log import configure_logging
from api.app.routers import experiments, health, recs, settings_llm, trace, users
from api.app.settings import Settings, get_settings

configure_logging()
logger = logging.getLogger(__name__)
app = FastAPI(title="RAGPoison API")

app.include_router(health.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(recs.router, prefix="/api")
app.include_router(trace.router, prefix="/api")
app.include_router(settings_llm.router, prefix="/api")
app.include_router(experiments.router, prefix="/api")
if not any(
    getattr(route, "path", None) == "/api/experiments/run"
    and "POST" in (getattr(route, "methods", set()) or set())
    for route in app.routes
):
    raise RuntimeError("Expected experiments orchestration route '/api/experiments/run' is not registered")
logger.info("api_route_registered route=/api/experiments/run method=POST")

assets_dir = get_settings().resolved_static_dir / "assets"
if assets_dir.exists() and assets_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/", include_in_schema=False)
def spa_index(settings: Settings = Depends(get_settings)) -> FileResponse:
    return _serve_spa_path("", settings=settings)


@app.get("/{full_path:path}", include_in_schema=False)
def spa_fallback(full_path: str, settings: Settings = Depends(get_settings)) -> FileResponse:
    if full_path.startswith("api"):
        raise HTTPException(status_code=404, detail="Not found")
    return _serve_spa_path(full_path, settings=settings)


def _serve_spa_path(full_path: str, *, settings: Settings) -> FileResponse:
    static_dir = settings.resolved_static_dir
    if full_path:
        maybe_static = _resolve_safe_static_path(static_dir, full_path)
        if maybe_static is not None and maybe_static.exists() and maybe_static.is_file():
            return FileResponse(maybe_static)

    index_file = static_dir / "index.html"
    if index_file.exists() and index_file.is_file():
        return FileResponse(index_file)

    raise HTTPException(status_code=404, detail="SPA assets not found")


def _resolve_safe_static_path(static_root: Path, relative: str) -> Path | None:
    candidate = (static_root / relative).resolve()
    root = static_root.resolve()
    if candidate == root or root in candidate.parents:
        return candidate
    return None
