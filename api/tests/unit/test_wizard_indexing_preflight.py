from __future__ import annotations

from pathlib import Path

import pytest

from api.app.cli import wizard
from api.app.settings import Settings


def test_indexing_screen_blocks_when_preflight_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    selections = iter(["baseline", "back"])
    outputs: list[str] = []
    called: dict[str, int] = {}

    monkeypatch.setattr(wizard, "get_settings", lambda: Settings(_env_file=None))
    monkeypatch.setattr(wizard, "_select", lambda *args, **kwargs: next(selections))
    monkeypatch.setattr(wizard, "_prompt_text", lambda *args, **kwargs: "http://localhost:9200")
    monkeypatch.setattr(wizard, "_prompt_path", lambda *args, **kwargs: Path("/tmp/processed"))
    monkeypatch.setattr(wizard, "preflight_es", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("tls failed")))
    monkeypatch.setattr(wizard, "_wait_for_enter", lambda: called.__setitem__("wait", called.get("wait", 0) + 1))
    monkeypatch.setattr(wizard, "index_baseline", lambda *args, **kwargs: called.__setitem__("baseline", 1))
    monkeypatch.setattr(wizard, "index_stats", lambda *args, **kwargs: {})
    monkeypatch.setattr(wizard, "_print_summary", lambda *args, **kwargs: None)
    monkeypatch.setattr(wizard.typer, "echo", lambda message="": outputs.append(str(message)))

    wizard._indexing_screen()

    assert called.get("baseline") is None
    assert called.get("wait") == 1
    assert any("Elasticsearch preflight failed" in line for line in outputs)


def test_indexing_screen_runs_when_preflight_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    selections = iter(["baseline", "back"])
    outputs: list[str] = []
    called: dict[str, object] = {}

    monkeypatch.setattr(wizard, "get_settings", lambda: Settings(_env_file=None))
    monkeypatch.setattr(wizard, "_select", lambda *args, **kwargs: next(selections))
    monkeypatch.setattr(wizard, "_prompt_text", lambda *args, **kwargs: "http://localhost:9200")
    monkeypatch.setattr(wizard, "_prompt_path", lambda *args, **kwargs: Path("/tmp/processed"))
    monkeypatch.setattr(
        wizard,
        "preflight_es",
        lambda *args, **kwargs: {"name": "es-node", "version": "8.19.11", "cluster_name": "docker-cluster"},
    )
    monkeypatch.setattr(
        wizard,
        "index_baseline",
        lambda *args, **kwargs: {"index": "movies", "indexed_docs": 1},
    )
    monkeypatch.setattr(wizard, "index_stats", lambda *args, **kwargs: {"movies": {"exists": True, "doc_count": 1}})
    monkeypatch.setattr(wizard, "_wait_for_enter", lambda: called.__setitem__("wait", True))
    monkeypatch.setattr(wizard, "_print_summary", lambda *args, **kwargs: called.__setitem__("printed", True))
    monkeypatch.setattr(wizard.typer, "echo", lambda message="": outputs.append(str(message)))

    wizard._indexing_screen()

    assert called.get("printed") is True
    assert called.get("wait") is True
    assert any("Elasticsearch preflight OK" in line for line in outputs)
