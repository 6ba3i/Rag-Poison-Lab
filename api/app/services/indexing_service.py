from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
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
PROVENANCE_META_KEY = "ragpoison_provenance"

ENV_MOVIES_MAPPING_PATH = "RAGPOISON_MOVIES_MAPPING_PATH"
ENV_MOVIES_POISONED_MAPPING_PATH = "RAGPOISON_MOVIES_POISONED_MAPPING_PATH"
ENV_ES_MAPPING_DIR = "RAGPOISON_ES_MAPPING_DIR"

MOVIES_MAPPING_PATH = REPO_ROOT / "docker" / "es" / "movies_index.json"
MOVIES_POISONED_MAPPING_PATH = REPO_ROOT / "docker" / "es" / "movies_poisoned_index.json"
PACKAGED_ES_MAPPING_DIR = Path(__file__).resolve().parents[1] / "resources" / "es"
PACKAGED_MOVIES_MAPPING_PATH = PACKAGED_ES_MAPPING_DIR / "movies_index.json"
PACKAGED_MOVIES_POISONED_MAPPING_PATH = PACKAGED_ES_MAPPING_DIR / "movies_poisoned_index.json"

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


def resolve_index_mapping_path(*, logical_index_name: str, mapping_path: Path | None = None) -> Path:
    filename: str
    env_path_var: str
    repo_default: Path
    packaged_default: Path

    if logical_index_name == INDEX_MOVIES:
        filename = "movies_index.json"
        env_path_var = ENV_MOVIES_MAPPING_PATH
        repo_default = MOVIES_MAPPING_PATH
        packaged_default = PACKAGED_MOVIES_MAPPING_PATH
    elif logical_index_name == INDEX_MOVIES_POISONED:
        filename = "movies_poisoned_index.json"
        env_path_var = ENV_MOVIES_POISONED_MAPPING_PATH
        repo_default = MOVIES_POISONED_MAPPING_PATH
        packaged_default = PACKAGED_MOVIES_POISONED_MAPPING_PATH
    else:
        raise ValueError(f"Unsupported logical index for mapping resolution: {logical_index_name}")

    candidates: list[Path] = []
    if mapping_path is not None:
        candidates.append(mapping_path)

    env_specific = _normalize_optional(os.environ.get(env_path_var))
    if env_specific is not None:
        candidates.append(Path(env_specific))

    env_dir = _normalize_optional(os.environ.get(ENV_ES_MAPPING_DIR))
    if env_dir is not None:
        candidates.append(Path(env_dir) / filename)

    candidates.append(repo_default)
    candidates.append(packaged_default)

    attempted: list[str] = []
    seen: set[str] = set()
    for raw_candidate in candidates:
        resolved_candidate = raw_candidate.expanduser().resolve()
        candidate_key = str(resolved_candidate)
        if candidate_key in seen:
            continue
        seen.add(candidate_key)
        attempted.append(candidate_key)
        if resolved_candidate.exists() and resolved_candidate.is_file():
            return resolved_candidate

    attempted_text = ", ".join(attempted) if attempted else "(none)"
    raise FileNotFoundError(
        f"Mapping file not found for index '{logical_index_name}'. Tried paths: {attempted_text}"
    )


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


def get_index_stats(*, es_url: str | None = None) -> dict[str, dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = {}
    base = _resolve_es_url(es_url)
    for index_name in (INDEX_MOVIES, INDEX_MOVIES_POISONED):
        exists = index_exists(index_name, es_url=es_url)
        count = doc_count(index_name, es_url=es_url) if exists else None
        alias_targets = _alias_targets(index_name, es_url=base)
        stats[index_name] = {"exists": exists, "doc_count": count, "physical_indices": alias_targets}
    return stats


def get_index_provenance(*, es_client: Any, logical_index_name: str) -> dict[str, Any] | None:
    indices = getattr(es_client, "indices", None)
    if indices is None:
        return None
    getter = getattr(indices, "get_mapping", None)
    if not callable(getter):
        return None

    response = getter(index=logical_index_name)
    payload = response if isinstance(response, dict) else dict(response)
    if not payload:
        return None
    first_index_name, first_mapping = next(iter(payload.items()))
    if not isinstance(first_mapping, dict):
        return None
    mappings = first_mapping.get("mappings")
    if not isinstance(mappings, dict):
        return None
    meta = mappings.get("_meta")
    if not isinstance(meta, dict):
        return None
    provenance = meta.get(PROVENANCE_META_KEY)
    if not isinstance(provenance, dict):
        return None
    return {
        "logical_index": logical_index_name,
        "physical_index": str(first_index_name),
        "provenance": provenance,
    }


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


def _load_bulk_payload(
    bulk_path: Path,
    *,
    expected_index_name: str,
    target_index_name: str,
) -> tuple[bytes, int, int]:
    if not bulk_path.exists():
        raise FileNotFoundError(f"Bulk JSONL file not found: {bulk_path}")
    if bulk_path.stat().st_size == 0:
        raise ValueError(f"Bulk JSONL file is empty: {bulk_path}")

    raw_lines = bulk_path.read_text(encoding="utf-8").splitlines()
    if not raw_lines:
        raise ValueError(f"Bulk JSONL file contains no lines: {bulk_path}")
    if len(raw_lines) % 2 != 0:
        raise ValueError(f"Bulk JSONL must contain action/document line pairs: {bulk_path}")

    poison_docs = 0
    normalized_lines: list[str] = []
    for line_idx in range(0, len(raw_lines), 2):
        try:
            action = json.loads(raw_lines[line_idx])
            document = json.loads(raw_lines[line_idx + 1])
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Invalid JSON in bulk file at lines {line_idx + 1}-{line_idx + 2}: {exc}") from exc

        if not isinstance(action, dict) or "index" not in action or not isinstance(action["index"], dict):
            raise ValueError(f"Invalid action line structure at line {line_idx + 1}")
        metadata = action["index"]
        action_index = metadata.get("_index")
        action_id = metadata.get("_id")
        if action_index != expected_index_name:
            raise ValueError(
                f"Bulk action index mismatch at line {line_idx + 1}: expected '{expected_index_name}', got '{action_index}'"
            )
        if not isinstance(action_id, str) or action_id == "":
            raise ValueError(f"Bulk action _id missing or invalid at line {line_idx + 1}")
        if not isinstance(document, dict):
            raise ValueError(f"Bulk document line must be a JSON object at line {line_idx + 2}")
        if str(document.get("movie_id", "")) != action_id:
            raise ValueError(f"movie_id must match action _id at lines {line_idx + 1}-{line_idx + 2}")
        if bool(document.get("poison_marker", False)):
            poison_docs += 1
        metadata["_index"] = target_index_name
        normalized_lines.append(json.dumps(action, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
        normalized_lines.append(json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False))

    payload = ("\n".join(normalized_lines) + "\n").encode("utf-8")
    expected_docs = len(normalized_lines) // 2
    return payload, expected_docs, poison_docs


def _hash_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _version_suffix(*, bulk_path: Path) -> str:
    digest = _hash_file(bulk_path)[:12]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{stamp}_{digest}"


def _build_physical_index_name(*, logical_alias: str, bulk_path: Path) -> str:
    return f"{logical_alias}__{_version_suffix(bulk_path=bulk_path)}"


def _create_index(index_name: str, *, mapping_path: Path, es_url: str) -> None:
    logger.info(
        "index_create_start phase=indexing index_name=%s es_url=%s mapping_path=%s",
        index_name,
        es_url,
        mapping_path,
    )
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
    logger.info("index_create_complete phase=indexing index_name=%s", index_name)


def _alias_targets(alias_name: str, *, es_url: str) -> list[str]:
    status, body = _request(method="GET", url=f"{es_url}/_alias/{alias_name}")
    if status == 404:
        return []
    if status != 200:
        raise RuntimeError(
            f"Failed to read alias '{alias_name}' (HTTP {status}): {body.decode('utf-8', errors='replace')}"
        )
    payload = _parse_json(body, context=f"alias response for '{alias_name}'")
    return sorted(str(key) for key in payload.keys())


def _switch_alias(*, alias_name: str, new_index: str, es_url: str) -> dict[str, Any]:
    previous = _alias_targets(alias_name, es_url=es_url)
    actions: list[dict[str, Any]] = []
    for index_name in previous:
        actions.append({"remove": {"index": index_name, "alias": alias_name}})
    actions.append({"add": {"index": new_index, "alias": alias_name}})

    status, body = _request(
        method="POST",
        url=f"{es_url}/_aliases",
        data=json.dumps({"actions": actions}).encode("utf-8"),
        content_type="application/json",
    )
    if status not in {200, 201}:
        raise RuntimeError(
            f"Failed to switch alias '{alias_name}' to '{new_index}' (HTTP {status}): "
            f"{body.decode('utf-8', errors='replace')}"
        )
    return {
        "alias": alias_name,
        "previous_indices": previous,
        "current_index": new_index,
    }


def _write_index_provenance_meta(*, index_name: str, provenance: dict[str, Any], es_url: str) -> None:
    status, body = _request(
        method="PUT",
        url=f"{es_url}/{index_name}/_mapping",
        data=json.dumps({"_meta": {PROVENANCE_META_KEY: provenance}}, sort_keys=True).encode("utf-8"),
        content_type="application/json",
    )
    if status not in {200, 201}:
        raise RuntimeError(
            f"Failed to write provenance metadata for '{index_name}' (HTTP {status}): "
            f"{body.decode('utf-8', errors='replace')}"
        )


def _bulk_index(
    logical_index_name: str,
    *,
    physical_index_name: str,
    bulk_path: Path,
    es_url: str,
) -> dict[str, Any]:
    payload, expected_docs, poison_docs = _load_bulk_payload(
        bulk_path,
        expected_index_name=logical_index_name,
        target_index_name=physical_index_name,
    )
    logger.info(
        "bulk_index_start phase=indexing logical_index=%s physical_index=%s es_url=%s bulk_path=%s expected_docs=%s poison_docs=%s",
        logical_index_name,
        physical_index_name,
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
            f"Bulk indexing failed for '{physical_index_name}' (HTTP {bulk_status}): "
            f"{bulk_body.decode('utf-8', errors='replace')}"
        )

    response = _parse_json(bulk_body, context=f"bulk response for '{physical_index_name}'")
    if bool(response.get("errors")):
        first_error: str | None = None
        for item in response.get("items", []):
            if not isinstance(item, dict):
                continue
            metadata = item.get("index")
            if isinstance(metadata, dict) and "error" in metadata:
                first_error = json.dumps(metadata["error"], sort_keys=True)
                break
        raise RuntimeError(
            f"Bulk indexing returned item errors for '{physical_index_name}': {first_error or 'unknown'}"
        )

    indexed_docs = doc_count(physical_index_name, es_url=es_url)
    if indexed_docs != expected_docs:
        raise RuntimeError(
            f"Document count mismatch for '{physical_index_name}': expected {expected_docs}, got {indexed_docs}"
        )
    logger.info(
        "bulk_index_complete phase=indexing logical_index=%s physical_index=%s expected_docs=%s indexed_docs=%s poison_docs=%s",
        logical_index_name,
        physical_index_name,
        expected_docs,
        indexed_docs,
        poison_docs,
    )

    return {
        "index": logical_index_name,
        "physical_index": physical_index_name,
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
    mapping_path: Path | None = None,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = _resolve_es_url(es_url)
    resolved_mapping_path = resolve_index_mapping_path(
        logical_index_name=INDEX_MOVIES,
        mapping_path=mapping_path,
    )
    bulk_path = _processed_dir(processed_dir) / ES_BULK_MOVIES_JSONL
    physical_index = _build_physical_index_name(logical_alias=INDEX_MOVIES, bulk_path=bulk_path)
    logger.info(
        "index_baseline_direct phase=indexing alias=%s physical_index=%s es_url=%s bulk_path=%s mapping_path=%s",
        INDEX_MOVIES,
        physical_index,
        base,
        bulk_path,
        resolved_mapping_path,
    )
    _create_index(physical_index, mapping_path=resolved_mapping_path, es_url=base)
    indexed = _bulk_index(INDEX_MOVIES, physical_index_name=physical_index, bulk_path=bulk_path, es_url=base)
    resolved_provenance = {
        "logical_index": INDEX_MOVIES,
        "physical_index": physical_index,
        "bulk_sha256": _hash_file(bulk_path),
        "mapping_sha256": _hash_file(resolved_mapping_path),
        "indexed_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    if provenance:
        resolved_provenance.update(provenance)
    _write_index_provenance_meta(index_name=physical_index, provenance=resolved_provenance, es_url=base)
    alias_state = _switch_alias(alias_name=INDEX_MOVIES, new_index=physical_index, es_url=base)
    return {
        **indexed,
        "alias": alias_state["alias"],
        "previous_indices": alias_state["previous_indices"],
        "current_index": alias_state["current_index"],
        "provenance": resolved_provenance,
    }


def index_poisoned_direct(
    *,
    es_url: str | None = None,
    processed_dir: str | Path | None = None,
    mapping_path: Path | None = None,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = _resolve_es_url(es_url)
    resolved_mapping_path = resolve_index_mapping_path(
        logical_index_name=INDEX_MOVIES_POISONED,
        mapping_path=mapping_path,
    )
    bulk_path = _processed_dir(processed_dir) / ES_BULK_POISONED_MOVIES_JSONL
    physical_index = _build_physical_index_name(logical_alias=INDEX_MOVIES_POISONED, bulk_path=bulk_path)
    logger.info(
        "index_poisoned_direct phase=indexing alias=%s physical_index=%s es_url=%s bulk_path=%s mapping_path=%s",
        INDEX_MOVIES_POISONED,
        physical_index,
        base,
        bulk_path,
        resolved_mapping_path,
    )
    _create_index(physical_index, mapping_path=resolved_mapping_path, es_url=base)
    indexed = _bulk_index(
        INDEX_MOVIES_POISONED,
        physical_index_name=physical_index,
        bulk_path=bulk_path,
        es_url=base,
    )
    resolved_provenance = {
        "logical_index": INDEX_MOVIES_POISONED,
        "physical_index": physical_index,
        "bulk_sha256": _hash_file(bulk_path),
        "mapping_sha256": _hash_file(resolved_mapping_path),
        "indexed_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    if provenance:
        resolved_provenance.update(provenance)
    _write_index_provenance_meta(index_name=physical_index, provenance=resolved_provenance, es_url=base)
    alias_state = _switch_alias(alias_name=INDEX_MOVIES_POISONED, new_index=physical_index, es_url=base)
    return {
        **indexed,
        "alias": alias_state["alias"],
        "previous_indices": alias_state["previous_indices"],
        "current_index": alias_state["current_index"],
        "provenance": resolved_provenance,
    }


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
    base = _resolve_es_url(es_url)
    output: dict[str, Any] = {}
    for alias_name in (INDEX_MOVIES, INDEX_MOVIES_POISONED):
        targets = _alias_targets(alias_name, es_url=base)
        deleted_targets: list[dict[str, Any]] = []
        for index_name in targets:
            deleted_targets.append(delete_index_if_exists(index_name, es_url=base))
        alias_direct_delete = delete_index_if_exists(alias_name, es_url=base)
        output[alias_name] = {
            "physical_indices_deleted": deleted_targets,
            "logical_index_deleted": alias_direct_delete,
        }
    return output
