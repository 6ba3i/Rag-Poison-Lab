from __future__ import annotations

from pathlib import Path

import pytest

from api.app.services import indexing_service


def _write_mapping(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"mappings":{"properties":{}}}\n', encoding="utf-8")


@pytest.mark.parametrize(
    ("logical_index", "repo_attr", "packaged_attr", "filename"),
    [
        (indexing_service.INDEX_MOVIES, "MOVIES_MAPPING_PATH", "PACKAGED_MOVIES_MAPPING_PATH", "movies_index.json"),
        (
            indexing_service.INDEX_MOVIES_POISONED,
            "MOVIES_POISONED_MAPPING_PATH",
            "PACKAGED_MOVIES_POISONED_MAPPING_PATH",
            "movies_poisoned_index.json",
        ),
    ],
)
def test_resolve_index_mapping_path_uses_repo_relative_default(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    logical_index: str,
    repo_attr: str,
    packaged_attr: str,
    filename: str,
) -> None:
    repo_mapping = tmp_path / "repo" / "docker" / "es" / filename
    _write_mapping(repo_mapping)
    monkeypatch.setattr(indexing_service, repo_attr, repo_mapping)
    monkeypatch.setattr(indexing_service, packaged_attr, tmp_path / "missing" / filename)
    monkeypatch.delenv(indexing_service.ENV_ES_MAPPING_DIR, raising=False)
    monkeypatch.delenv(indexing_service.ENV_MOVIES_MAPPING_PATH, raising=False)
    monkeypatch.delenv(indexing_service.ENV_MOVIES_POISONED_MAPPING_PATH, raising=False)

    resolved = indexing_service.resolve_index_mapping_path(logical_index_name=logical_index)
    assert resolved == repo_mapping.resolve()


@pytest.mark.parametrize(
    ("logical_index", "repo_attr", "packaged_attr", "filename"),
    [
        (indexing_service.INDEX_MOVIES, "MOVIES_MAPPING_PATH", "PACKAGED_MOVIES_MAPPING_PATH", "movies_index.json"),
        (
            indexing_service.INDEX_MOVIES_POISONED,
            "MOVIES_POISONED_MAPPING_PATH",
            "PACKAGED_MOVIES_POISONED_MAPPING_PATH",
            "movies_poisoned_index.json",
        ),
    ],
)
def test_resolve_index_mapping_path_uses_mapping_dir_override_when_repo_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    logical_index: str,
    repo_attr: str,
    packaged_attr: str,
    filename: str,
) -> None:
    env_mapping_dir = tmp_path / "env_mappings"
    env_mapping = env_mapping_dir / filename
    _write_mapping(env_mapping)
    monkeypatch.setattr(indexing_service, repo_attr, tmp_path / "missing_repo" / filename)
    monkeypatch.setattr(indexing_service, packaged_attr, tmp_path / "missing_packaged" / filename)
    monkeypatch.setenv(indexing_service.ENV_ES_MAPPING_DIR, str(env_mapping_dir))
    monkeypatch.delenv(indexing_service.ENV_MOVIES_MAPPING_PATH, raising=False)
    monkeypatch.delenv(indexing_service.ENV_MOVIES_POISONED_MAPPING_PATH, raising=False)

    resolved = indexing_service.resolve_index_mapping_path(logical_index_name=logical_index)
    assert resolved == env_mapping.resolve()


@pytest.mark.parametrize(
    ("logical_index", "repo_attr", "packaged_attr", "filename"),
    [
        (indexing_service.INDEX_MOVIES, "MOVIES_MAPPING_PATH", "PACKAGED_MOVIES_MAPPING_PATH", "movies_index.json"),
        (
            indexing_service.INDEX_MOVIES_POISONED,
            "MOVIES_POISONED_MAPPING_PATH",
            "PACKAGED_MOVIES_POISONED_MAPPING_PATH",
            "movies_poisoned_index.json",
        ),
    ],
)
def test_resolve_index_mapping_path_uses_packaged_fallback_when_repo_absent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    logical_index: str,
    repo_attr: str,
    packaged_attr: str,
    filename: str,
) -> None:
    packaged_mapping = tmp_path / "packaged" / filename
    _write_mapping(packaged_mapping)
    monkeypatch.setattr(indexing_service, repo_attr, tmp_path / "missing_repo" / filename)
    monkeypatch.setattr(indexing_service, packaged_attr, packaged_mapping)
    monkeypatch.delenv(indexing_service.ENV_ES_MAPPING_DIR, raising=False)
    monkeypatch.delenv(indexing_service.ENV_MOVIES_MAPPING_PATH, raising=False)
    monkeypatch.delenv(indexing_service.ENV_MOVIES_POISONED_MAPPING_PATH, raising=False)

    resolved = indexing_service.resolve_index_mapping_path(logical_index_name=logical_index)
    assert resolved == packaged_mapping.resolve()
