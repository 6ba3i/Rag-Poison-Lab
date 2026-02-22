from __future__ import annotations

import pytest

from api.app.eval.metrics import asr_at_k, hr_at_k, mean_metrics, metrics_delta, mrr_at_k, ndcg_at_k


def test_hr_ndcg_mrr_at_k_basic() -> None:
    recommended = [10, 20, 30, 40]
    relevant = {20, 50}

    assert hr_at_k(recommended, relevant, 3) == 1.0
    assert mrr_at_k(recommended, relevant, 3) == 0.5

    ndcg = ndcg_at_k(recommended, relevant, 3)
    assert 0.0 < ndcg <= 1.0


def test_metric_edge_cases() -> None:
    assert hr_at_k([], {1, 2}, 10) == 0.0
    assert ndcg_at_k([1, 2], set(), 10) == 0.0
    assert mrr_at_k([1, 2], {3}, 10) == 0.0
    assert asr_at_k([1, 2, 3], None, 10) == 0.0
    assert asr_at_k([1, 2, 3], 2, 0) == 0.0


def test_asr_at_k_detects_target() -> None:
    assert asr_at_k([7, 8, 9], 8, 10) == 1.0
    assert asr_at_k([7, 8, 9], 10, 10) == 0.0


def test_mean_and_delta_helpers() -> None:
    rows = [
        {"hr": 1.0, "ndcg": 0.5},
        {"hr": 0.0, "ndcg": 0.25},
    ]
    mean = mean_metrics(rows, ["hr", "ndcg", "mrr"])
    assert mean["hr"] == 0.5
    assert mean["ndcg"] == 0.375
    assert mean["mrr"] == 0.0

    delta = metrics_delta(baseline={"hr": 0.4, "ndcg": 0.6}, attacked={"hr": 0.2, "ndcg": 0.9})
    assert delta["hr"] == pytest.approx(-0.2)
    assert delta["ndcg"] == pytest.approx(0.3)
