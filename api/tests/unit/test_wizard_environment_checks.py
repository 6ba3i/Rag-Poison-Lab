from __future__ import annotations

from pathlib import Path

import pytest

from api.app.cli import wizard
from api.app.settings import Settings


def test_environment_checks_use_resolved_runtime_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    dataset_dir = tmp_path / "ml-100"
    data_dir = tmp_path / "data"
    dataset_dir.mkdir(parents=True)
    data_dir.mkdir(parents=True)

    settings = Settings(_env_file=None, data_root=data_dir)
    outputs: list[str] = []

    class _Registry:
        def __init__(self, *, settings: Settings) -> None:
            self.settings = settings

        def ollama_connectivity(self) -> bool:
            return True

    monkeypatch.setattr(wizard, "get_settings", lambda: settings)
    monkeypatch.setattr(wizard, "resolve_default_dataset_dir", lambda: dataset_dir)
    monkeypatch.setattr(wizard, "LlmRegistry", _Registry)
    monkeypatch.setattr(
        wizard,
        "_check_http",
        lambda name, url, *, fix, optional=False: {"name": name, "status": "PASS", "detail": url, "fix": fix},
    )
    monkeypatch.setattr(wizard, "resolve_api_key", lambda *args, **kwargs: (None, "missing"))
    monkeypatch.setattr(wizard, "_wait_for_enter", lambda: None)
    monkeypatch.setattr(wizard.typer, "echo", lambda message="": outputs.append(str(message)))

    wizard._environment_checks_screen()

    assert any(f"[PASS] Dataset directory exists: {dataset_dir}" in line for line in outputs)
    assert any(f"[PASS] Data directory writable: {data_dir}" in line for line in outputs)
    assert not any("/workspace/ml-100 exists" in line for line in outputs)
    assert not any("/workspace/data writable" in line for line in outputs)


def test_path_fix_hint_container_path() -> None:
    assert wizard._path_fix_hint(path=Path("/workspace/data"), host_fix="ignored") == "Bind-mount ./data to /workspace/data"
    assert wizard._path_fix_hint(path=Path("/tmp/data"), host_fix="host fix") == "host fix"
