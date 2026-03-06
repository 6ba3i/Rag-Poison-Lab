from __future__ import annotations

from pathlib import Path

import pytest

from api.app.services import indexing_service
from api.app.settings import Settings, get_es_client


def test_settings_default_elasticsearch_url_is_localhost(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ELASTICSEARCH_URL", raising=False)
    settings = Settings(_env_file=None)
    assert settings.elasticsearch_url == "http://localhost:9200"


def test_settings_elasticsearch_url_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ELASTICSEARCH_URL", "http://example-es:9200")
    settings = Settings(_env_file=None)
    assert settings.elasticsearch_url == "http://example-es:9200"


def test_settings_elasticsearch_external_options_parse(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    ca_path = tmp_path / "ca.pem"
    ca_path.write_text("dummy-ca", encoding="utf-8")
    monkeypatch.setenv("ELASTICSEARCH_USERNAME", "alice")
    monkeypatch.setenv("ELASTICSEARCH_PASSWORD", "secret")
    monkeypatch.setenv("ELASTICSEARCH_API_KEY", "key-123")
    monkeypatch.setenv("ELASTICSEARCH_VERIFY_SSL", "false")
    monkeypatch.setenv("ELASTICSEARCH_CA_BUNDLE", str(ca_path))
    monkeypatch.setenv("ELASTICSEARCH_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setenv("OLLAMA_TIMEOUT_SECONDS", "75")

    settings = Settings(_env_file=None)
    assert settings.elasticsearch_username == "alice"
    assert settings.elasticsearch_password == "secret"
    assert settings.elasticsearch_api_key == "key-123"
    assert settings.elasticsearch_verify_ssl is False
    assert settings.elasticsearch_ca_bundle == ca_path
    assert settings.elasticsearch_timeout_seconds == 12.5
    assert settings.ollama_timeout_seconds == 75.0


def test_resolve_es_url_falls_back_to_default_when_env_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ELASTICSEARCH_URL", raising=False)
    assert indexing_service._resolve_es_url(None) == "http://localhost:9200"


def test_resolve_es_url_prefers_env_over_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ELASTICSEARCH_URL", "http://env-es:9200/")
    assert indexing_service._resolve_es_url(None) == "http://env-es:9200"


def test_resolve_es_url_prefers_explicit_over_env_and_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ELASTICSEARCH_URL", "http://env-es:9200")
    assert indexing_service._resolve_es_url("http://explicit-es:9200/") == "http://explicit-es:9200"


def test_connection_hint_for_localhost_connection_refused() -> None:
    err = OSError(111, "Connection refused")
    hint = indexing_service._connection_hint("http://localhost:9200/movies", exc=err)
    assert hint is not None
    assert "not listening on localhost:9200" in hint


def test_connection_hint_for_compose_dns_name_resolution_failure() -> None:
    err = OSError(-2, "Name or service not known")
    hint = indexing_service._connection_hint("http://elasticsearch:9200/movies", exc=err)
    assert hint is not None
    assert "Docker Compose internal DNS" in hint


def test_compose_app_service_overrides_elasticsearch_url() -> None:
    compose_path = Path(__file__).resolve().parents[3] / "docker" / "docker-compose.yml"
    compose_text = compose_path.read_text(encoding="utf-8")
    assert "ELASTICSEARCH_URL: http://elasticsearch:9200" in compose_text


def test_get_es_client_prefers_api_key_over_basic_auth(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ELASTICSEARCH_URL", "http://localhost:9200")
    monkeypatch.setenv("ELASTICSEARCH_USERNAME", "alice")
    monkeypatch.setenv("ELASTICSEARCH_PASSWORD", "secret")
    monkeypatch.setenv("ELASTICSEARCH_API_KEY", "api-key-value")
    monkeypatch.setenv("ELASTICSEARCH_VERIFY_SSL", "true")
    monkeypatch.setenv("ELASTICSEARCH_TIMEOUT_SECONDS", "8")
    monkeypatch.setenv("ELASTICSEARCH_CA_BUNDLE", str(tmp_path / "ca.pem"))
    (tmp_path / "ca.pem").write_text("ca", encoding="utf-8")

    from api.app import settings as settings_module

    captured: dict[str, object] = {}

    def fake_build_es_client(
        es_url: str,
        *,
        api_key: str | None,
        username: str | None,
        password: str | None,
        verify_ssl: bool,
        ca_bundle: Path | None,
        timeout_seconds: float,
    ) -> object:
        captured["es_url"] = es_url
        captured["api_key"] = api_key
        captured["username"] = username
        captured["password"] = password
        captured["verify_ssl"] = verify_ssl
        captured["ca_bundle"] = ca_bundle
        captured["timeout_seconds"] = timeout_seconds
        return object()

    monkeypatch.setattr(settings_module, "_build_es_client", fake_build_es_client)
    settings_module.get_settings.cache_clear()
    _ = get_es_client()
    assert captured["es_url"] == "http://localhost:9200"
    assert captured["api_key"] == "api-key-value"
    assert captured["username"] == "alice"
    assert captured["password"] == "secret"
    assert captured["verify_ssl"] is True
    assert captured["timeout_seconds"] == 8.0
    settings_module.get_settings.cache_clear()
