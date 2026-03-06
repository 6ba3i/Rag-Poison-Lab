from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from api.app.services import indexing_service
from api.app.settings import Settings


def _build_settings(tmp_path: Path, **overrides: object) -> Settings:
    defaults: dict[str, object] = {
        "elasticsearch_url": "http://localhost:9200",
        "elasticsearch_verify_ssl": True,
        "elasticsearch_timeout_seconds": 10.0,
        "data_root": tmp_path / "data",
        "config_root": tmp_path / "data" / "config",
        "processed_root": tmp_path / "data" / "processed",
    }
    defaults.update(overrides)
    settings = Settings(_env_file=None, **defaults)
    settings.resolved_config_dir.mkdir(parents=True, exist_ok=True)
    settings.resolved_processed_dir.mkdir(parents=True, exist_ok=True)
    return settings


def test_preflight_success_returns_banner(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    monkeypatch.setattr(indexing_service, "get_settings", lambda: settings)

    def fake_request(**kwargs):  # type: ignore[no-untyped-def]
        return httpx.Response(
            status_code=200,
            json={"name": "es-node", "cluster_name": "docker-cluster", "version": {"number": "8.19.11"}},
            request=httpx.Request(kwargs["method"], kwargs["url"]),
        )

    monkeypatch.setattr(indexing_service.httpx, "request", fake_request)
    banner = indexing_service.preflight_es(es_url="http://localhost:9200")
    assert banner["name"] == "es-node"
    assert banner["cluster_name"] == "docker-cluster"
    assert banner["version"] == "8.19.11"


def test_request_prefers_api_key_over_basic_auth(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = _build_settings(
        tmp_path,
        elasticsearch_api_key="key-abc",
        elasticsearch_username="alice",
        elasticsearch_password="secret",
    )
    monkeypatch.setattr(indexing_service, "get_settings", lambda: settings)
    captured: dict[str, object] = {}

    def fake_request(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return httpx.Response(200, json={"ok": True}, request=httpx.Request(kwargs["method"], kwargs["url"]))

    monkeypatch.setattr(indexing_service.httpx, "request", fake_request)
    status, _ = indexing_service._request(method="GET", url="http://localhost:9200/_cluster/health")
    assert status == 200
    assert captured["auth"] is None
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["Authorization"] == "ApiKey key-abc"


def test_request_uses_basic_auth_when_no_api_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = _build_settings(
        tmp_path,
        elasticsearch_username="alice",
        elasticsearch_password="secret",
    )
    monkeypatch.setattr(indexing_service, "get_settings", lambda: settings)
    captured: dict[str, object] = {}

    def fake_request(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return httpx.Response(200, json={"ok": True}, request=httpx.Request(kwargs["method"], kwargs["url"]))

    monkeypatch.setattr(indexing_service.httpx, "request", fake_request)
    status, _ = indexing_service._request(method="GET", url="http://localhost:9200/")
    assert status == 200
    assert captured["auth"] == ("alice", "secret")
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert "Authorization" not in headers


def test_request_ssl_verify_options(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    ca_bundle = tmp_path / "ca.pem"
    ca_bundle.write_text("ca", encoding="utf-8")
    settings = _build_settings(tmp_path, elasticsearch_verify_ssl=True, elasticsearch_ca_bundle=ca_bundle)
    monkeypatch.setattr(indexing_service, "get_settings", lambda: settings)
    captured: dict[str, object] = {}

    def fake_request(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return httpx.Response(200, json={"ok": True}, request=httpx.Request(kwargs["method"], kwargs["url"]))

    monkeypatch.setattr(indexing_service.httpx, "request", fake_request)
    indexing_service._request(method="GET", url="https://remote-es:9243/")
    assert captured["verify"] == str(ca_bundle.resolve())

    settings_no_verify = _build_settings(tmp_path, elasticsearch_verify_ssl=False)
    monkeypatch.setattr(indexing_service, "get_settings", lambda: settings_no_verify)
    indexing_service._request(method="GET", url="https://remote-es:9243/")
    assert captured["verify"] is False


def test_request_timeout_from_settings_and_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = _build_settings(tmp_path, elasticsearch_timeout_seconds=12.5)
    monkeypatch.setattr(indexing_service, "get_settings", lambda: settings)
    captured: dict[str, object] = {}

    def fake_request(**kwargs):  # type: ignore[no-untyped-def]
        captured["timeout"] = kwargs["timeout"]
        return httpx.Response(200, json={"ok": True}, request=httpx.Request(kwargs["method"], kwargs["url"]))

    monkeypatch.setattr(indexing_service.httpx, "request", fake_request)
    indexing_service._request(method="GET", url="http://localhost:9200/")
    assert captured["timeout"] == 12.5

    indexing_service._request(method="GET", url="http://localhost:9200/", timeout=120)
    assert captured["timeout"] == 120.0


def test_preflight_connection_refused_message(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    monkeypatch.setattr(indexing_service, "get_settings", lambda: settings)

    def fake_request(**kwargs):  # type: ignore[no-untyped-def]
        req = httpx.Request(kwargs["method"], kwargs["url"])
        raise httpx.ConnectError("connection failed", request=req) from OSError(111, "Connection refused")

    monkeypatch.setattr(indexing_service.httpx, "request", fake_request)
    with pytest.raises(RuntimeError, match="not listening on localhost:9200") as exc_info:
        indexing_service.preflight_es(es_url="http://localhost:9200")
    message = str(exc_info.value)
    assert "docker-compose.dev.yml" in message
    assert "http://elasticsearch:9200" in message


def test_preflight_tls_error_message(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    monkeypatch.setattr(indexing_service, "get_settings", lambda: settings)

    def fake_request(**kwargs):  # type: ignore[no-untyped-def]
        req = httpx.Request(kwargs["method"], kwargs["url"])
        raise httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] bad cert", request=req)

    monkeypatch.setattr(indexing_service.httpx, "request", fake_request)
    with pytest.raises(RuntimeError, match="TLS handshake/certificate validation failed"):
        indexing_service.preflight_es(es_url="https://remote-es:9243")


def test_preflight_timeout_message(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = _build_settings(tmp_path, elasticsearch_timeout_seconds=1.0)
    monkeypatch.setattr(indexing_service, "get_settings", lambda: settings)

    def fake_request(**kwargs):  # type: ignore[no-untyped-def]
        req = httpx.Request(kwargs["method"], kwargs["url"])
        raise httpx.ConnectTimeout("timed out", request=req)

    monkeypatch.setattr(indexing_service.httpx, "request", fake_request)
    with pytest.raises(RuntimeError, match="timed out"):
        indexing_service.preflight_es(es_url="https://remote-es:9243")


def test_request_unauthorized_message(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = _build_settings(tmp_path)
    monkeypatch.setattr(indexing_service, "get_settings", lambda: settings)

    def fake_request(**kwargs):  # type: ignore[no-untyped-def]
        return httpx.Response(
            status_code=401,
            json={"error": "security_exception"},
            request=httpx.Request(kwargs["method"], kwargs["url"]),
        )

    monkeypatch.setattr(indexing_service.httpx, "request", fake_request)
    with pytest.raises(RuntimeError, match="Authentication failed"):
        indexing_service._request(method="GET", url="https://remote-es:9243/")
