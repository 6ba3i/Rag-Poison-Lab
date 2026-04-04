from __future__ import annotations

import pytest

from api.app.cli import wizard


class _TextPrompt:
    def __init__(self, answer: str) -> None:
        self._answer = answer

    def ask(self) -> str:
        return self._answer


def test_prompt_int_accepts_bounded_target_boost_strength(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        wizard.questionary,
        "text",
        lambda *args, **kwargs: _TextPrompt("7"),
    )

    value = wizard._prompt_int(
        "Target boost strength (1-20)",
        4,
        minimum=1,
        maximum=20,
    )

    assert value == 7


def test_prompt_int_rejects_bounded_target_boost_strength_out_of_range(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        wizard.questionary,
        "text",
        lambda *args, **kwargs: _TextPrompt("21"),
    )

    with pytest.raises(ValueError, match="Value must be between 1 and 20"):
        wizard._prompt_int(
            "Target boost strength (1-20)",
            4,
            minimum=1,
            maximum=20,
        )
