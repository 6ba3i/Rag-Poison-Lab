from __future__ import annotations

import math
from typing import Mapping, Sequence


MetricMap = dict[str, float]


def hr_at_k(recommended: Sequence[int], relevant: set[int] | Sequence[int], k: int) -> float:
    if k <= 0:
        return 0.0
    relevant_set = _relevant_set(relevant)
    if not relevant_set:
        return 0.0
    top_k = _top_k(recommended, k)
    return 1.0 if any(movie_id in relevant_set for movie_id in top_k) else 0.0


def ndcg_at_k(recommended: Sequence[int], relevant: set[int] | Sequence[int], k: int) -> float:
    if k <= 0:
        return 0.0

    relevant_set = _relevant_set(relevant)
    if not relevant_set:
        return 0.0

    top_k = _top_k(recommended, k)
    dcg = 0.0
    for rank, movie_id in enumerate(top_k, start=1):
        if movie_id in relevant_set:
            dcg += 1.0 / math.log2(rank + 1)

    ideal_hits = min(len(relevant_set), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    if idcg == 0.0:
        return 0.0
    return dcg / idcg


def mrr_at_k(recommended: Sequence[int], relevant: set[int] | Sequence[int], k: int) -> float:
    if k <= 0:
        return 0.0

    relevant_set = _relevant_set(relevant)
    if not relevant_set:
        return 0.0

    top_k = _top_k(recommended, k)
    for rank, movie_id in enumerate(top_k, start=1):
        if movie_id in relevant_set:
            return 1.0 / float(rank)
    return 0.0


def asr_at_k(recommended: Sequence[int], target_movie_id: int | None, k: int) -> float:
    if k <= 0 or target_movie_id is None:
        return 0.0
    top_k = _top_k(recommended, k)
    return 1.0 if int(target_movie_id) in top_k else 0.0


def mean_metrics(rows: Sequence[Mapping[str, float]], metric_keys: Sequence[str]) -> MetricMap:
    output: MetricMap = {}
    if not rows:
        for key in metric_keys:
            output[key] = 0.0
        return output

    count = float(len(rows))
    for key in metric_keys:
        output[key] = sum(float(row.get(key, 0.0)) for row in rows) / count
    return output


def metrics_delta(*, baseline: Mapping[str, float], attacked: Mapping[str, float]) -> MetricMap:
    keys = sorted(set(baseline.keys()) | set(attacked.keys()))
    return {
        key: float(attacked.get(key, 0.0)) - float(baseline.get(key, 0.0))
        for key in keys
    }


def metric_stats(values: Sequence[float]) -> dict[str, float | int | None]:
    if not values:
        return {
            "count": 0,
            "mean": 0.0,
            "stddev": 0.0,
            "stderr": 0.0,
            "ci95_low": None,
            "ci95_high": None,
        }

    count = len(values)
    mean = sum(float(item) for item in values) / float(count)
    if count <= 1:
        return {
            "count": count,
            "mean": mean,
            "stddev": 0.0,
            "stderr": 0.0,
            "ci95_low": None,
            "ci95_high": None,
        }

    variance = sum((float(item) - mean) ** 2 for item in values) / float(count - 1)
    stddev = math.sqrt(max(variance, 0.0))
    stderr = stddev / math.sqrt(float(count))
    margin = 1.96 * stderr
    return {
        "count": count,
        "mean": mean,
        "stddev": stddev,
        "stderr": stderr,
        "ci95_low": mean - margin,
        "ci95_high": mean + margin,
    }


def paired_significance(values: Sequence[float]) -> dict[str, float | int | str | None]:
    positive = sum(1 for item in values if float(item) > 0.0)
    negative = sum(1 for item in values if float(item) < 0.0)
    ties = sum(1 for item in values if float(item) == 0.0)
    effective_n = positive + negative
    if effective_n == 0:
        return {
            "count": 0,
            "positive": positive,
            "negative": negative,
            "ties": ties,
            "p_value": None,
            "method": "paired_sign_test",
            "direction": None,
        }

    tail = min(positive, negative)
    probability = 0.0
    for k in range(0, tail + 1):
        probability += math.comb(effective_n, k)
    p_value = min(1.0, 2.0 * probability / float(2**effective_n))
    direction = "positive" if positive > negative else "negative" if negative > positive else "tie"
    return {
        "count": effective_n,
        "positive": positive,
        "negative": negative,
        "ties": ties,
        "p_value": p_value,
        "method": "paired_sign_test",
        "direction": direction,
    }


def _top_k(recommended: Sequence[int], k: int) -> list[int]:
    output: list[int] = []
    seen: set[int] = set()
    for raw in recommended:
        try:
            movie_id = int(raw)
        except Exception:  # noqa: BLE001
            continue
        if movie_id in seen:
            continue
        seen.add(movie_id)
        output.append(movie_id)
        if len(output) >= k:
            break
    return output


def _relevant_set(relevant: set[int] | Sequence[int]) -> set[int]:
    output: set[int] = set()
    for raw in relevant:
        try:
            output.add(int(raw))
        except Exception:  # noqa: BLE001
            continue
    return output
