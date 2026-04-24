from __future__ import annotations

from api.app.llm.model_catalog import (
    filter_anthropic_model_ids,
    filter_deepseek_model_ids,
    filter_gemini_model_ids,
    filter_openai_model_ids,
    filter_qwen_model_ids,
)
from api.app.llm.openai_responses_client import _extract_text


def test_openai_catalog_filters_to_current_text_gpt_models() -> None:
    models = [
        {"id": "gpt-3.5-turbo"},
        {"id": "gpt-4"},
        {"id": "gpt-4.1"},
        {"id": "gpt-4o"},
        {"id": "gpt-4o-mini"},
        {"id": "gpt-4o-mini-search-preview"},
        {"id": "gpt-5"},
        {"id": "gpt-5-chat-latest"},
        {"id": "gpt-5-codex"},
        {"id": "gpt-5-search-api"},
        {"id": "gpt-5.4"},
        {"id": "gpt-5.4-mini"},
        {"id": "gpt-5.4-pro"},
        {"id": "gpt-audio"},
    ]

    assert filter_openai_model_ids(models) == [
        "gpt-4.1",
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-5",
        "gpt-5-chat-latest",
        "gpt-5-codex",
        "gpt-5.4",
        "gpt-5.4-mini",
        "gpt-5.4-pro",
    ]


def test_anthropic_catalog_keeps_current_claude_ids() -> None:
    models = [
        {"id": "claude-opus-4-7"},
        {"id": "claude-sonnet-4-6"},
        {"id": "something-else"},
        {"id": "claude-opus-4-1-20250805"},
    ]

    assert filter_anthropic_model_ids(models) == [
        "claude-opus-4-7",
        "claude-sonnet-4-6",
        "claude-opus-4-1-20250805",
    ]


def test_gemini_catalog_filters_to_generate_content_text_models() -> None:
    models = [
        {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-2.5-pro", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-2.5-flash-native-audio-latest", "supportedGenerationMethods": ["bidiGenerateContent"]},
        {"name": "models/gemini-3-pro-preview", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-3.1-flash-tts-preview", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-embedding-001", "supportedGenerationMethods": ["embedContent"]},
    ]

    assert filter_gemini_model_ids(models) == [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-3-pro-preview",
    ]


def test_qwen_catalog_filters_to_safe_compatible_text_models() -> None:
    compat = [
        {"id": "qwen3.6-plus"},
        {"id": "qwen3-max-preview"},
        {"id": "qwen-coder-plus-latest"},
        {"id": "qwen3-235b-a22b-thinking-2507"},
        {"id": "qwen3-asr-flash-realtime"},
        {"id": "qwen-image-2.0"},
    ]
    models = [
        {"model": "qwen3.6-plus", "inference_metadata": {"response_modality": ["Text"]}},
        {"model": "qwen3-max-preview", "inference_metadata": {"response_modality": ["Text"]}},
        {"model": "qwen-coder-plus-latest", "inference_metadata": {"response_modality": ["Text"]}},
        {"model": "qwen3-235b-a22b-thinking-2507", "inference_metadata": {"response_modality": ["Text"]}},
        {"model": "qwen3-asr-flash-realtime", "inference_metadata": {"response_modality": ["Text"]}},
        {"model": "qwen-image-2.0", "inference_metadata": {"response_modality": ["Text"]}},
        {"model": "qwen3.6-plus", "inference_metadata": {"response_modality": ["Text"]}},
    ]

    assert filter_qwen_model_ids(compat_data=compat, model_data=models) == [
        "qwen3.6-plus",
        "qwen3-max-preview",
    ]


def test_deepseek_catalog_filters_to_text_models() -> None:
    models = [
        {"id": "deepseek-chat"},
        {"id": "deepseek-reasoner"},
        {"id": "deepseek-vl"},
        {"id": "deepseek-audio"},
        {"id": "something-else"},
        {"id": "deepseek-chat"},
    ]

    assert filter_deepseek_model_ids(models) == [
        "deepseek-chat",
        "deepseek-reasoner",
    ]


def test_openai_responses_extractor_prefers_output_text() -> None:
    body = {"output_text": "{\"items\":[]}"}
    assert _extract_text(body) == "{\"items\":[]}"


def test_openai_responses_extractor_falls_back_to_output_content() -> None:
    body = {
        "output": [
            {
                "content": [
                    {"type": "output_text", "text": "hello"},
                    {"type": "output_text", "text": "world"},
                ]
            }
        ]
    }
    assert _extract_text(body) == "hello\nworld"
