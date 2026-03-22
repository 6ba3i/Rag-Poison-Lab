from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os
import socket
import ssl
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from api.app.data.paths import (
    ES_BULK_MOVIES_JSONL,
    ES_BULK_POISONED_MOVIES_JSONL,
    REPO_ROOT,
    resolve_output_dir,
)
from api.app.settings import Settings, get_settings

DEFAULT_ES_URL = "http://localhost:9200"
INDEX_MOVIES = "movies"
INDEX_MOVIES_POISONED = "movies_poisoned"

MOVIES_MAPPING_PATH = REPO_ROOT / "docker" / "es" / "movies_index.json"
MOVIES_POISONED_MAPPING_PATH = REPO_ROOT / "docker" / "es" / "movies_poisoned_index.json"

CONNECT_REFUSED_ERRNOS = {111, 61, 10061}
DNS_ERRNOS = {-2, 8, 11001}

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _EsHttpConfig:
    headers: dict[str, str]
    basic_auth: tuple[str, str] | None
    verify: bool | str
    timeout_seconds: float


def _resolve_es_url(es_url: str | None = None) -> str:
    resolved = es_url or os.environ.get("ELASTICSEARCH_URL") or DEFAULT_ES_URL
    return resolved.rstrip("/")


def _normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _resolve_http_config(settings: Settings | None = None) -> _EsHttpConfig:
    resolved_settings = settings or get_settings()
    api_key = _normalize_optional(resolved_settings.elasticsearch_api_key)
    username = _normalize_optional(resolved_settings.elasticsearch_username)
    password = _normalize_optional(resolved_settings.elasticsearch_password)

    headers: dict[str, str] = {}
    basic_auth: tuple[str, str] | None = None
    if api_key is not None:
        headers["Authorization"] = f"ApiKey {api_key}"
    elif username is not None and password is not None:
        basic_auth = (username, password)

    if not resolved_settings.elasticsearch_verify_ssl:
        verify: bool | str = False
    elif resolved_settings.elasticsearch_ca_bundle is not None:
        verify = str(resolved_settings.elasticsearch_ca_bundle.resolve())
    else:
        verify = True

    return _EsHttpConfig(
        headers=headers,
        basic_auth=basic_auth,
        verify=verify,
        timeout_seconds=float(resolved_settings.elasticsearch_timeout_seconds),
    )


def _host_and_port(url: str) -> tuple[str, int]:
    parsed = urlparse(url)
    host = parsed.hostname or "unknown-host"
    if parsed.port is not None:
        return host, parsed.port
    return host, 443 if parsed.scheme == "https" else 80


def _iter_exc_chain(exc: BaseException) -> list[BaseException]:
    chain: list[BaseException] = []
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        chain.append(current)
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return chain


def _request(
    *,
    method: str,
    url: str,
    data: bytes | None = None,
    content_type: str | None = None,
    timeout: float | None = None,
    settings: Settings | None = None,
) -> tuple[int, bytes]:
    config = _resolve_http_config(settings=settings)
    request_timeout = float(timeout) if timeout is not None else config.timeout_seconds
    headers = dict(config.headers)
    if content_type is not None:
        headers["Content-Type"] = content_type

    try:
        response = httpx.request(
            method=method,
            url=url,
            content=data,
            headers=headers,
            auth=config.basic_auth,
            timeout=request_timeout,
            verify=config.verify,
            follow_redirects=True,
        )
    except httpx.RequestError as exc:
        hint = _connection_hint(url, exc=exc)
        if hint:
            raise RuntimeError(f"Failed to connect to Elasticsearch at {url}: {exc}\nHint: {hint}") from exc
        raise RuntimeError(f"Failed to connect to Elasticsearch at {url}: {exc}") from exc

    if response.status_code in {401, 403}:
        hint = _connection_hint(url, status_code=response.status_code)
        body = response.text.strip()
        message = (
            f"Elasticsearch request failed at {url} (HTTP {response.status_code}). "
            f"{body if body else 'Authentication/authorization failed.'}"
        )
        if hint:
            message = f"{message}\nHint: {hint}"
        raise RuntimeError(message)

    return response.status_code, response.content


def _connection_hint(url: str, exc: Exception | None = None, *, status_code: int | None = None) -> str | None:
    hostname, port = _host_and_port(url)
    hostname = hostname.lower()

    if status_code in {401, 403}:
        return (
            "Authentication failed. Set ELASTICSEARCH_API_KEY, or ELASTICSEARCH_USERNAME and "
            "ELASTICSEARCH_PASSWORD. API key auth takes precedence when both are set."
        )

    if exc is None:
        return None

    if isinstance(exc, httpx.TimeoutException):
        return (
            f"Connection to {hostname}:{port} timed out. Verify network reachability and increase "
            "ELASTICSEARCH_TIMEOUT_SECONDS if needed."
        )

    for chain_exc in _iter_exc_chain(exc):
        if isinstance(chain_exc, ssl.SSLError):
            return (
                "TLS handshake/certificate validation failed. Set ELASTICSEARCH_CA_BUNDLE to a trusted "
                "CA bundle, or set ELASTICSEARCH_VERIFY_SSL=false for local/dev environments."
            )
        if isinstance(chain_exc, socket.gaierror) and getattr(chain_exc, "errno", None) in DNS_ERRNOS:
            if hostname == "elasticsearch":
                return (
                    "Hostname 'elasticsearch' is Docker Compose internal DNS. Use it only inside compose containers. "
                    "From host shell, use http://localhost:9200 (or your external Elasticsearch URL)."
                )
            return f"DNS resolution failed for '{hostname}'. Verify the host name and network DNS configuration."
        if isinstance(chain_exc, OSError):
            errno = getattr(chain_exc, "errno", None)
            if errno in CONNECT_REFUSED_ERRNOS:
                if hostname in {"localhost", "127.0.0.1", "::1"}:
                    return (
                        f"Elasticsearch is not listening on {hostname}:{port}. "
                        "If Docker Compose is running with only docker/docker-compose.yml, port 9200 is not "
                        "published to the host. For host-run uv commands, publish ES with: "
                        "docker compose -f docker/docker-compose.yml -f docker/docker-compose.dev.yml up -d --build. "
                        "If running the wizard inside the RagPoison container, use "
                        "ELASTICSEARCH_URL=http://elasticsearch:9200."
                    )
                return f"Connection refused to {hostname}:{port}. Verify host, port, and firewall/network policy."
            if errno in DNS_ERRNOS:
                if hostname == "elasticsearch":
                    return (
                        "Hostname 'elasticsearch' is Docker Compose internal DNS. Use it only inside compose containers. "
                        "From host shell, use http://localhost:9200 (or your external Elasticsearch URL)."
                    )
                return f"DNS resolution failed for '{hostname}'. Verify the host name and network DNS configuration."

    message = str(exc).lower()
    if "certificate verify failed" in message or "tls" in message or "ssl" in message:
        return (
            "TLS handshake/certificate validation failed. Set ELASTICSEARCH_CA_BUNDLE to a trusted "
            "CA bundle, or set ELASTICSEARCH_VERIFY_SSL=false for local/dev environments."
        )
    if "name or service not known" in message or "temporary failure in name resolution" in message:
        return f"DNS resolution failed for '{hostname}'. Verify the host name and network DNS configuration."
    if "connection refused" in message:
        return f"Connection refused to {hostname}:{port}. Verify host, port, and Elasticsearch service status."

    return None


def preflight_es(*, es_url: str | None = None, settings: Settings | None = None) -> dict[str, Any]:
    base_url = _resolve_es_url(es_url)
    logger.info("es_preflight_start phase=indexing es_url=%s", base_url)
    status, body = _request(method="GET", url=f"{base_url}/", settings=settings)
    if status < 200 or status >= 300:
        raise RuntimeError(
            f"Elasticsearch preflight failed at {base_url}/ (HTTP {status}): "
            f"{body.decode('utf-8', errors='replace')}"
        )

    payload = _parse_json(body, context=f"preflight response for '{base_url}'")
    version = payload.get("version")
    version_number = version.get("number") if isinstance(version, dict) else None
    return {
        "url": base_url,
        "name": payload.get("name"),
        "cluster_name": payload.get("cluster_name"),
        "version": version_number,
    }


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


def _load_bulk_payload(bulk_path: Path, *, index_name: str) -> tuple[bytes, int, int]:
    if not bulk_path.exists():
        raise FileNotFoundError(f"Bulk JSONL file not found: {bulk_path}")
    if bulk_path.stat().st_size == 0:
        raise ValueError(f"Bulk JSONL file is empty: {bulk_path}")

    lines = bulk_path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError(f"Bulk JSONL file contains no lines: {bulk_path}")
    if len(lines) % 2 != 0:
        raise ValueError(f"Bulk JSONL must contain action/document line pairs: {bulk_path}")

    poison_docs = 0
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
        if bool(document.get("poison_marker", False)):
            poison_docs += 1

    payload = ("\n".join(lines) + "\n").encode("utf-8")
    expected_docs = len(lines) // 2
    return payload, expected_docs, poison_docs


def _ensure_index(index_name: str, *, mapping_path: Path, es_url: str) -> None:
    logger.info(
        "index_ensure_start phase=indexing index_name=%s es_url=%s mapping_path=%s",
        index_name,
        es_url,
        mapping_path,
    )
    status, _ = _request(method="HEAD", url=f"{es_url}/{index_name}")
    if status == 200:
        logger.info("index_ensure_exists phase=indexing index_name=%s", index_name)
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
    logger.info("index_created phase=indexing index_name=%s", index_name)


def _bulk_index(index_name: str, *, bulk_path: Path, es_url: str) -> dict[str, Any]:
    payload, expected_docs, poison_docs = _load_bulk_payload(bulk_path, index_name=index_name)
    logger.info(
        "bulk_index_start phase=indexing index_name=%s es_url=%s bulk_path=%s expected_docs=%s poison_docs=%s",
        index_name,
        es_url,
        bulk_path,
        expected_docs,
        poison_docs,
    )
    # Use the global bulk API; each action line already carries its own `_index`.
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
    logger.info(
        "bulk_index_complete phase=indexing index_name=%s expected_docs=%s indexed_docs=%s poison_docs=%s",
        index_name,
        expected_docs,
        indexed_docs,
        poison_docs,
    )

    return {
        "index": index_name,
        "bulk_file": str(bulk_path),
        "expected_docs": expected_docs,
        "indexed_docs": indexed_docs,
        "poison_docs": poison_docs,
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
    logger.info(
        "index_baseline_direct phase=indexing index_name=%s es_url=%s bulk_path=%s mapping_path=%s",
        INDEX_MOVIES,
        base,
        bulk_path,
        mapping_path,
    )
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
    logger.info(
        "index_poisoned_direct phase=indexing index_name=%s es_url=%s bulk_path=%s mapping_path=%s",
        INDEX_MOVIES_POISONED,
        base,
        bulk_path,
        mapping_path,
    )
    _ensure_index(INDEX_MOVIES_POISONED, mapping_path=mapping_path, es_url=base)
    return _bulk_index(INDEX_MOVIES_POISONED, bulk_path=bulk_path, es_url=base)


def delete_index_if_exists(index_name: str, *, es_url: str | None = None) -> dict[str, Any]:
    base = _resolve_es_url(es_url)
    status, _ = _request(method="HEAD", url=f"{base}/{index_name}")
    if status == 404:
        return {
            "index": index_name,
            "existed": False,
            "deleted": False,
        }
    if status != 200:
        raise RuntimeError(f"Failed to check index '{index_name}' before delete (HTTP {status})")

    delete_status, delete_body = _request(method="DELETE", url=f"{base}/{index_name}")
    if delete_status not in {200, 202}:
        raise RuntimeError(
            f"Failed to delete index '{index_name}' (HTTP {delete_status}): "
            f"{delete_body.decode('utf-8', errors='replace')}"
        )

    return {
        "index": index_name,
        "existed": True,
        "deleted": True,
    }


def reset_indices(*, es_url: str | None = None) -> dict[str, Any]:
    return {
        INDEX_MOVIES: delete_index_if_exists(INDEX_MOVIES, es_url=es_url),
        INDEX_MOVIES_POISONED: delete_index_if_exists(INDEX_MOVIES_POISONED, es_url=es_url),
    }
