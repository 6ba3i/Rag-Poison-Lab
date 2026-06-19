from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.app.cli import wizard
from api.app.main import app
from api.app.services.orchestration_service import ExperimentRunOptions, plan_experiment_run


def _patch_wizard_single_inputs(
    monkeypatch: pytest.MonkeyPatch,
    *,
    label: str,
    k: int,
    user_id_text: str,
) -> None:
    selections = iter(["single", "back"])
    monkeypatch.setattr(wizard, "_select", lambda *args, **kwargs: next(selections))
    monkeypatch.setattr(
        wizard,
        "_prompt_text",
        lambda message, default: label
        if message == "Run label"
        else (user_id_text if message == "User ID (leave blank for auto viable selection)" else default),
    )
    monkeypatch.setattr(wizard, "_prompt_int", lambda *args, **kwargs: k)
    monkeypatch.setattr(wizard, "_wait_for_enter", lambda: None)
    monkeypatch.setattr(wizard, "_print_summary", lambda *args, **kwargs: None)
    monkeypatch.setattr(wizard.typer, "echo", lambda *args, **kwargs: None)


def test_single_demo_planner_defaults_and_override() -> None:
    base = ExperimentRunOptions(
        label="x",
        mode="single",
        k=10,
        user_id=None,
        batch_size=1,
        run_profile="single_demo",
        run_prepare=None,
        run_index=None,
        run_eval=None,
        run_report=None,
        overwrite=False,
        dataset_dir=None,
        output_dir=None,
        es_url=None,
        attack_config=None,
        repeat_count=1,
        seed=42,
    )
    resolved = plan_experiment_run(options=base)
    assert resolved.run_prepare is False
    assert resolved.run_index is False
    assert resolved.run_eval is True
    assert resolved.run_report is True

    overridden = plan_experiment_run(
        options=ExperimentRunOptions(
            **{**base.__dict__, "run_prepare": True, "run_index": True, "run_eval": False, "run_report": True}
        )
    )
    assert overridden.run_prepare is True
    assert overridden.run_index is True
    assert overridden.run_eval is False
    assert overridden.run_report is True


def test_api_and_wizard_single_demo_use_same_resolved_options(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[ExperimentRunOptions] = []

    class _FakeOrchestrator:
        def run(self, *, options: ExperimentRunOptions) -> dict[str, Any]:
            captured.append(options)
            return {
                "label": options.label,
                "prepare": None,
                "index": None,
                "eval": {"target_movie_source": "auto_viable_pair", "selected_user_ids": [13]},
                "report": None,
                "run_dir": None,
            }

    monkeypatch.setattr("api.app.routers.experiments.ExperimentOrchestrator", _FakeOrchestrator)
    monkeypatch.setattr(wizard, "ExperimentOrchestrator", _FakeOrchestrator)

    with TestClient(app) as client:
        response = client.post(
            "/api/experiments/run",
            json={"label": "parity_case", "mode": "single", "run_profile": "single_demo", "k": 10},
        )
    assert response.status_code == 200

    _patch_wizard_single_inputs(monkeypatch, label="parity_case", k=10, user_id_text="")
    wizard._run_experiments_screen()

    assert len(captured) == 2
    api_opts, wizard_opts = captured
    assert api_opts.mode == wizard_opts.mode == "single"
    assert api_opts.run_profile == wizard_opts.run_profile == "single_demo"
    assert api_opts.k == wizard_opts.k == 10
    assert api_opts.user_id is None and wizard_opts.user_id is None

    api_resolved = plan_experiment_run(options=api_opts)
    wizard_resolved = plan_experiment_run(options=wizard_opts)
    assert api_resolved == wizard_resolved
    assert api_resolved.run_prepare is False
    assert api_resolved.run_index is False
    assert api_resolved.run_eval is True
    assert api_resolved.run_report is True


def test_api_and_wizard_single_demo_fail_with_same_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    message = (
        "Unable to auto-select a viable single-user targeted case. "
        "No user satisfied: baseline_relevant_hits_at_k>0, target not in train history, and "
        "target retrievable from attacked candidates. Provide --user-id manually or update attack_config target/movie setup."
    )

    class _FailingOrchestrator:
        def run(self, *, options: ExperimentRunOptions) -> dict[str, Any]:
            raise RuntimeError(message)

    monkeypatch.setattr("api.app.routers.experiments.ExperimentOrchestrator", _FailingOrchestrator)
    monkeypatch.setattr(wizard, "ExperimentOrchestrator", _FailingOrchestrator)

    with TestClient(app) as client:
        response = client.post(
            "/api/experiments/run",
            json={"label": "parity_fail", "mode": "single", "run_profile": "single_demo", "k": 10},
        )
    assert response.status_code == 409
    assert response.json()["detail"] == message

    _patch_wizard_single_inputs(monkeypatch, label="parity_fail", k=10, user_id_text="")
    with pytest.raises(RuntimeError, match="Unable to auto-select a viable single-user targeted case"):
        wizard._run_experiments_screen()


def test_single_demo_user_override_is_consistent(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[ExperimentRunOptions] = []

    class _FakeOrchestrator:
        def run(self, *, options: ExperimentRunOptions) -> dict[str, Any]:
            captured.append(options)
            return {"label": options.label, "prepare": None, "index": None, "eval": {}, "report": None, "run_dir": None}

    monkeypatch.setattr("api.app.routers.experiments.ExperimentOrchestrator", _FakeOrchestrator)
    monkeypatch.setattr(wizard, "ExperimentOrchestrator", _FakeOrchestrator)

    with TestClient(app) as client:
        response = client.post(
            "/api/experiments/run",
            json={
                "label": "parity_user_override",
                "mode": "single",
                "run_profile": "single_demo",
                "k": 15,
                "user_id": 13,
            },
        )
    assert response.status_code == 200

    _patch_wizard_single_inputs(monkeypatch, label="parity_user_override", k=15, user_id_text="13")
    wizard._run_experiments_screen()

    assert len(captured) == 2
    api_opts, wizard_opts = captured
    assert api_opts.user_id == wizard_opts.user_id == 13
    assert api_opts.k == wizard_opts.k == 15
    assert plan_experiment_run(options=api_opts) == plan_experiment_run(options=wizard_opts)
