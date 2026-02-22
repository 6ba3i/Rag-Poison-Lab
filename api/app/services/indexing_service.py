from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
import urllib.error
import urllib.request

from api.app.data.paths import (
    ES_BULK_MOVIES_JSONL,
    ES_BULK_POISONED_MOVIES_JSONL,
    REPO_ROOT,
    resolve_output_dir,
)

DEFAULT_ES_URL = "http://elasticsearch:9200"
INDEX_MOVIES = "movies"
INDEX_MOVIES_POISONED = "movies_poisoned"

MOVIES_MAPPING_PATH = REPO_ROOT / "docker" / "es" / "movies_index.json"
MOVIES_POISONED_MAPPING_PATH = REPO_ROOT / "docker" / "es" / "movies_poisoned_index.json"


def _resolve_es_url(es_url: str | None = None) -> str:
    resolved = es_url or os.environ.get("ELASTICSEARCH_URL") or DEFAULT_ES_URL
    return resolved.rstrip("/")


def _request(
    *,
    method: str,
    url: str,
    data: bytes | None = None,
    content_type: str | None = None,
    timeout: int = 30,
) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=data, method=method)
    if content_type is not None:
        request.add_header("Content-Type", content_type)

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Failed to connect to Elasticsearch at {url}: {exc}") from exc


def _parse_json(body: bytes, *, context: str) -> dict[str, Any]:
    try:
        parsed = json.loads(body.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"{context}: invalid JSON response: {exc}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"{context}: expected JSON object")
    return parsed


def index_exists(index_name: str, *, es_url: str | None = None) -> bool:
    base = _resolve_es_url(es_url)
    status, _ = _request(method="HEAD", url=f"{base}/{index_name}")
    if status == 200:
        return True
    if status == 404:
        return False
    raise RuntimeError(f"Failed to check index '{index_name}' (HTTP {status})")


def doc_count(index_name: str, *, es_url: str | None = None) -> int:
    base = _resolve_es_url(es_url)
    status, body = _request(method="GET", url=f"{base}/{index_name}/_count")
    if status != 200:
        raise RuntimeError(
            f"Failed to fetch document count for '{index_name}' (HTTP {status}): "
            f"{body.decode('utf-8', errors='replace')}"
        )
    payload = _parse_json(body, context=f"count response for '{index_name}'")
    count_raw = payload.get("count")
    if not isinstance(count_raw, int):
        raise RuntimeError(f"Count response for '{index_name}' did not contain an integer 'count'")
    return count_raw


def get_index_stats(*, es_url: str | None = None) -> dict[str, dict[str, int | bool | None]]:
    stats: dict[str, dict[str, int | bool | None]] = {}
    for index_name in (INDEX_MOVIES, INDEX_MOVIES_POISONED):
        exists = index_exists(index_name, es_url=es_url)
        count = doc_count(index_name, es_url=es_url) if exists else None
        stats[index_name] = {"exists": exists, "doc_count": count}
    return stats


def _load_mapping(mapping_path: Path) -> dict[str, Any]:
    if not mapping_path.exists():
        raise FileNotFoundError(f"Mapping file not found: {mapping_path}")
    if mapping_path.stat().st_size == 0:
        raise ValueError(f"Mapping file is empty: {mapping_path}")

    try:
        mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Mapping file is not valid JSON ({mapping_path}): {exc}") from exc

    if not isinstance(mapping, dict):
        raise ValueError(f"Mapping file must contain a JSON object: {mapping_path}")
    return mapping


def _load_bulk_payload(bulk_path: Path, *, index_name: str) -> tuple[bytes, int]:
    if not bulk_path.exists():
        raise FileNotFoundError(f"Bulk JSONL file not found: {bulk_path}")
    if bulk_path.stat().st_size == 0:
        raise ValueError(f"Bulk JSONL file is empty: {bulk_path}")

    lines = bulk_path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError(f"Bulk JSONL file contains no lines: {bulk_path}")
    if len(lines) % 2 != 0:
        raise ValueError(f"Bulk JSONL must contain action/document line pairs: {bulk_path}")

    for line_idx in range(0, len(lines), 2):
        try:
            action = json.loads(lines[line_idx])
            document = json.loads(lines[line_idx + 1])
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Invalid JSON in bulk file at lines {line_idx + 1}-{line_idx + 2}: {exc}") from exc

        if not isinstance(action, dict) or "index" not in action or not isinstance(action["index"], dict):
            raise ValueError(f"Invalid action line structure at line {line_idx + 1}")
        metadata = action["index"]
        action_index = metadata.get("_index")
        action_id = metadata.get("_id")
        if action_index != index_name:
            raise ValueError(
                f"Bulk action index mismatch at line {line_idx + 1}: expected '{index_name}', got '{action_index}'"
            )
        if not isinstance(action_id, str) or action_id == "":
            raise ValueError(f"Bulk action _id missing or invalid at line {line_idx + 1}")
        if not isinstance(document, dict):
            raise ValueError(f"Bulk document line must be a JSON object at line {line_idx + 2}")
        if str(document.get("movie_id", "")) != action_id:
            raise ValueError(f"movie_id must match action _id at lines {line_idx + 1}-{line_idx + 2}")

    payload = ("\n".join(lines) + "\n").encode("utf-8")
    expected_docs = len(lines) // 2
    return payload, expected_docs


def _ensure_index(index_name: str, *, mapping_path: Path, es_url: str) -> None:
    status, _ = _request(method="HEAD", url=f"{es_url}/{index_name}")
    if status == 200:
        return
    if status != 404:
        raise RuntimeError(f"Failed to check index '{index_name}' (HTTP {status})")

    mapping = _load_mapping(mapping_path)
    create_status, create_body = _request(
        method="PUT",
        url=f"{es_url}/{index_name}",
        data=json.dumps(mapping).encode("utf-8"),
        content_type="application/json",
    )
    if create_status not in {200, 201}:
        raise RuntimeError(
            f"Failed to create index '{index_name}' (HTTP {create_status}): "
            f"{create_body.decode('utf-8', errors='replace')}"
        )


def _bulk_index(index_name: str, *, bulk_path: Path, es_url: str) -> dict[str, Any]:
    payload, expected_docs = _load_bulk_payload(bulk_path, index_name=index_name)
    bulk_status, bulk_body = _request(
        method="POST",
        url=f"{es_url}/_bulk?refresh=true",
        data=payload,
        content_type="application/x-ndjson",
        timeout=120,
    )
    if bulk_status != 200:
        raise RuntimeError(
            f"Bulk indexing failed for '{index_name}' (HTTP {bulk_status}): "
            f"{bulk_body.decode('utf-8', errors='replace')}"
        )

    response = _parse_json(bulk_body, context=f"bulk response for '{index_name}'")
    if bool(response.get("errors")):
        first_error: str | None = None
        for item in response.get("items", []):
            if not isinstance(item, dict):
                continue
            metadata = item.get("index")
            if isinstance(metadata, dict) and "error" in metadata:
                first_error = json.dumps(metadata["error"], sort_keys=True)
                break
        raise RuntimeError(f"Bulk indexing returned item errors for '{index_name}': {first_error or 'unknown'}")

    indexed_docs = doc_count(index_name, es_url=es_url)
    if indexed_docs != expected_docs:
        raise RuntimeError(
            f"Document count mismatch for '{index_name}': expected {expected_docs}, got {indexed_docs}"
        )

    return {
        "index": index_name,
        "bulk_file": str(bulk_path),
        "expected_docs": expected_docs,
        "indexed_docs": indexed_docs,
    }


def _processed_dir(processed_dir: str | Path | None = None) -> Path:
    return resolve_output_dir(processed_dir, create=False)


def index_baseline_direct(
    *,
    es_url: str | None = None,
    processed_dir: str | Path | None = None,
    mapping_path: Path = MOVIES_MAPPING_PATH,
) -> dict[str, Any]:
    base = _resolve_es_url(es_url)
    bulk_path = _processed_dir(processed_dir) / ES_BULK_MOVIES_JSONL
    _ensure_index(INDEX_MOVIES, mapping_path=mapping_path, es_url=base)
    return _bulk_index(INDEX_MOVIES, bulk_path=bulk_path, es_url=base)


def index_poisoned_direct(
    *,
    es_url: str | None = None,
    processed_dir: str | Path | None = None,
    mapping_path: Path = MOVIES_POISONED_MAPPING_PATH,
) -> dict[str, Any]:
    base = _resolve_es_url(es_url)
    bulk_path = _processed_dir(processed_dir) / ES_BULK_POISONED_MOVIES_JSONL
    _ensure_index(INDEX_MOVIES_POISONED, mapping_path=mapping_path, es_url=base)
    return _bulk_index(INDEX_MOVIES_POISONED, bulk_path=bulk_path, es_url=base)
