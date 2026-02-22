from __future__ import annotations

import json
from pathlib import Path

import pytest

from api.app.llm import local_ollama, openai_compatible
from api.app.llm.local_ollama import LocalOllamaProvider
from api.app.llm.providers_chatgpt import ChatGptProvider
from api.app.llm.providers_qwen import QwenProvider
from api.app.llm.registry import LlmRegistry
from api.app.settings import Settings


class FakeResponse:
    def __init__(self, status_code: int, payload: object) -> None:
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> object:
        return self._payload


def test_local_ollama_provider_health_list_and_generate(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_payload: dict[str, object] = {}

    def fake_get(url: str, timeout: float) -> FakeResponse:
        assert url.endswith("/api/tags")
        assert timeout == 3.0
        return FakeResponse(
            200,
            {
                "models": [
                    {"name": "qwen2.5:1.5b"},
                    {"name": "phi3:mini"},
                    {"name": "phi3:mini"},
                ]
            },
        )

    def fake_post(url: str, json: dict[str, object], timeout: float) -> FakeResponse:
        assert url.endswith("/api/generate")
        assert timeout == 20.0
        captured_payload.update(json)
        return FakeResponse(200, {"response": "generated text"})

    monkeypatch.setattr(local_ollama.httpx, "get", fake_get)
    monkeypatch.setattr(local_ollama.httpx, "post", fake_post)

    provider = LocalOllamaProvider(base_url="http://ollama:11434", model="phi3:mini")
    assert provider.healthcheck().healthy is True
    assert provider.list_models() == ["phi3:mini", "qwen2.5:1.5b"]

    output = provider.generate(
        prompt="recommend a movie",
        system="short answer only",
        json_schema={"type": "object"},
        temperature=0.3,
        max_tokens=42,
    )
    assert output == "generated text"
    assert captured_payload["model"] == "phi3:mini"
    assert captured_payload["stream"] is False

    options = captured_payload.get("options")
    assert isinstance(options, dict)
    assert options["temperature"] == 0.3
    assert options["num_predict"] == 42


def test_chatgpt_provider_generate_with_secret(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    secret_path = tmp_path / "chatgpt_api_key.txt"
    secret_path.write_text("test-openai-key\n", encoding="utf-8")

    captured: dict[str, object] = {}

    def fake_post(url: str, headers: dict[str, str], json: dict[str, object], timeout: float) -> FakeResponse:
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse(200, {"choices": [{"message": {"content": "chatgpt output"}}]})

    monkeypatch.setattr(openai_compatible.httpx, "post", fake_post)

    provider = ChatGptProvider(
        model="gpt-4o-mini",
        api_key_file=secret_path,
        curated_models=["gpt-4o", "gpt-4o-mini"],
    )
    text = provider.generate(prompt="hello", system="be brief")

    assert text == "chatgpt output"
    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["timeout"] == 30.0

    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["Authorization"] == "Bearer test-openai-key"

    payload = captured["json"]
    assert isinstance(payload, dict)
    assert payload["model"] == "gpt-4o-mini"
    assert provider.list_models() == ["gpt-4o", "gpt-4o-mini"]
    assert provider.healthcheck().available is True


def test_cloud_provider_missing_key_and_mvp_stub(tmp_path: Path) -> None:
    missing_secret = tmp_path / "missing_chatgpt.txt"
    chatgpt = ChatGptProvider(model="gpt-4o", api_key_file=missing_secret, curated_models=[])
    status = chatgpt.healthcheck()
    assert status.available is False
    with pytest.raises(RuntimeError, match="missing API key secret file"):
        chatgpt.generate(prompt="hello")

    qwen_secret = tmp_path / "qwen_api_key.txt"
    qwen_secret.write_text("qwen-key\n", encoding="utf-8")
    qwen = QwenProvider(model="qwen-plus", api_key_file=qwen_secret, curated_models=["qwen-plus"])
    qwen_status = qwen.healthcheck()
    assert qwen_status.available is True
    assert qwen_status.healthy is False
    with pytest.raises(NotImplementedError, match="not implemented in MVP"):
        qwen.generate(prompt="hello")


def test_registry_provider_mapping_and_role_reload(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    config_dir = data_dir / "config"
    conf_dir = tmp_path / "conf"
    secrets_dir = tmp_path / "secrets"

    config_dir.mkdir(parents=True, exist_ok=True)
    conf_dir.mkdir(parents=True, exist_ok=True)
    secrets_dir.mkdir(parents=True, exist_ok=True)

    (conf_dir / "llm_models.yaml").write_text(
        "\n".join(
            [
                "chatgpt:",
                "  - gpt-4o",
                "  - gpt-4o-mini",
                "claude:",
                "  - claude-3-5-haiku",
                "gemini:",
                "  - gemini-2.0-flash",
                "qwen:",
                "  - qwen-plus",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (secrets_dir / "chatgpt_api_key.txt").write_text("chatgpt-key\n", encoding="utf-8")

    settings = Settings(
        data_root=data_dir,
        config_root=config_dir,
        llm_models_file=conf_dir / "llm_models.yaml",
        chatgpt_api_key_file=secrets_dir / "chatgpt_api_key.txt",
        claude_api_key_file=secrets_dir / "claude_api_key.txt",
        gemini_api_key_file=secrets_dir / "gemini_api_key.txt",
        qwen_api_key_file=secrets_dir / "qwen_api_key.txt",
    )
    registry = LlmRegistry(settings=settings)
    monkeypatch.setattr(registry, "list_local_models", lambda: ["phi3:mini"])

    options = {item.provider: item for item in registry.list_provider_options()}
    assert options["local"].available is True
    assert options["chatgpt"].available is True
    assert options["claude"].available is False
    assert options["chatgpt"].models == ["gpt-4o", "gpt-4o-mini"]

    first_config = {
        "victim": {"provider": "local", "model": "phi3:mini"},
        "attacker": {"provider": "chatgpt", "model": "gpt-4o"},
    }
    settings.resolved_llm_config_path.write_text(json.dumps(first_config), encoding="utf-8")

    victim_client = registry.get_victim_client()
    attacker_client = registry.get_attacker_client()
    assert victim_client.provider_name == "local"
    assert victim_client.model == "phi3:mini"
    assert attacker_client.provider_name == "chatgpt"
    assert attacker_client.model == "gpt-4o"

    second_config = {
        "victim": {"provider": "chatgpt", "model": "gpt-4o-mini"},
        "attacker": {"provider": "local", "model": "qwen2.5:1.5b"},
    }
    settings.resolved_llm_config_path.write_text(json.dumps(second_config), encoding="utf-8")

    victim_client_after = registry.get_victim_client()
    attacker_client_after = registry.get_attacker_client()
    assert victim_client_after.provider_name == "chatgpt"
    assert victim_client_after.model == "gpt-4o-mini"
    assert attacker_client_after.provider_name == "local"
    assert attacker_client_after.model == "qwen2.5:1.5b"
