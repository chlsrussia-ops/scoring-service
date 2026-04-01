"""Ranking metrics: nDCG, precision@k, recall@k, hit_rate, MAP, calibration."""
from __future__ import annotations

import math
from typing import Any


def precision_at_k(relevant: list[bool], k: int) -> float:
    """Precision@k: fraction of top-k items that are relevant."""
    if k <= 0:
        return 0.0
    top_k = relevant[:k]
    if not top_k:
        return 0.0
    return sum(1 for r in top_k if r) / len(top_k)


def recall_at_k(relevant: list[bool], k: int, total_relevant: int) -> float:
    """Recall@k: fraction of all relevant items found in top-k."""
    if total_relevant <= 0:
        return 0.0
    top_k = relevant[:k]
    return sum(1 for r in top_k if r) / total_relevant


def hit_rate(relevant: list[bool], k: int) -> float:
    """Hit rate@k: 1.0 if any relevant item in top-k, else 0.0."""
    return 1.0 if any(relevant[:k]) else 0.0


def ndcg_at_k(relevance_grades: list[int], k: int) -> float:
    """nDCG@k: normalized discounted cumulative gain.
    
    relevance_grades: list of graded relevance (0=irrelevant, higher=more relevant)
    """
    if k <= 0 or not relevance_grades:
        return 0.0

    def dcg(grades: list[int], n: int) -> float:
        result = 0.0
        for i, g in enumerate(grades[:n]):
            result += (2 ** g - 1) / math.log2(i + 2)
        return result

    actual_dcg = dcg(relevance_grades, k)
    ideal_grades = sorted(relevance_grades, reverse=True)
    ideal_dcg = dcg(ideal_grades, k)

    if ideal_dcg == 0:
        return 0.0
    return actual_dcg / ideal_dcg


def mean_average_precision(ranked_lists: list[list[bool]]) -> float:
    """MAP: mean of average precisions across multiple queries/lists."""
    if not ranked_lists:
        return 0.0
    
    aps = []
    for relevant in ranked_lists:
        ap = average_precision(relevant)
        aps.append(ap)
    return sum(aps) / len(aps)


def average_precision(relevant: list[bool]) -> float:
    """Average precision for a single ranked list."""
    if not relevant or not any(relevant):
        return 0.0
    
    precisions = []
    relevant_count = 0
    for i, is_rel in enumerate(relevant):
        if is_rel:
            relevant_count += 1
            precisions.append(relevant_count / (i + 1))
    
    return sum(precisions) / sum(1 for r in relevant if r)


def score_distribution_stats(scores: list[float]) -> dict[str, float]:
    """Distribution diagnostics for predicted scores."""
    if not scores:
        return {}
    
    sorted_s = sorted(scores)
    n = len(sorted_s)
    mean_val = sum(sorted_s) / n
    
    variance = sum((s - mean_val) ** 2 for s in sorted_s) / n
    std_val = math.sqrt(variance) if variance > 0 else 0.0
    
    return {
        "count": n,
        "mean": round(mean_val, 4),
        "std": round(std_val, 4),
        "min": round(sorted_s[0], 4),
        "max": round(sorted_s[-1], 4),
        "p25": round(sorted_s[n // 4], 4),
        "median": round(sorted_s[n // 2], 4),
        "p75": round(sorted_s[3 * n // 4], 4),
    }


def calibration_error(predicted_scores: list[float], actual_labels: list[bool], n_bins: int = 10) -> dict[str, Any]:
    """Expected calibration error — how well scores predict actual relevance."""
    if not predicted_scores or not actual_labels:
        return {"ece": 0.0, "bins": []}
    
    pairs = list(zip(predicted_scores, actual_labels))
    pairs.sort(key=lambda x: x[0])
    
    bin_size = max(1, len(pairs) // n_bins)
    bins = []
    total_ece = 0.0
    
    for i in range(0, len(pairs), bin_size):
        chunk = pairs[i:i + bin_size]
        avg_score = sum(p[0] for p in chunk) / len(chunk)
        avg_label = sum(1 for p in chunk if p[1]) / len(chunk)
        bin_error = abs(avg_score - avg_label)
        total_ece += bin_error * len(chunk)
        bins.append({
            "avg_predicted": round(avg_score, 4),
            "avg_actual": round(avg_label, 4),
            "count": len(chunk),
            "error": round(bin_error, 4),
        })
    
    ece = total_ece / len(pairs) if pairs else 0.0
    return {"ece": round(ece, 4), "bins": bins}


def compute_all_metrics(
    items: list[dict[str, Any]],
    k_values: list[int] | None = None,
) -> dict[str, float]:
    """Compute all ranking metrics from evaluation items.
    
    Each item should have:
    - predicted_rank or predicted_score
    - is_hit (bool)
    - relevance_grade (int, optional)
    """
    if not items:
        return {}
    
    if k_values is None:
        k_values = [3, 5, 10, 20]
    
    # Sort by predicted_rank (or predicted_score desc)
    items_sorted = sorted(items, key=lambda x: (x.get("predicted_rank") or 9999, -(x.get("predicted_score") or 0)))
    
    relevant = [bool(item.get("is_hit", False)) for item in items_sorted]
    total_relevant = sum(1 for r in relevant if r)
    
    grades = [item.get("relevance_grade", 1 if item.get("is_hit") else 0) for item in items_sorted]
    scores = [item.get("predicted_score", 0.0) for item in items_sorted if item.get("predicted_score") is not None]
    
    metrics: dict[str, float] = {}
    
    for k in k_values:
        if k > len(items_sorted):
            continue
        metrics[f"precision@{k}"] = round(precision_at_k(relevant, k), 4)
        metrics[f"recall@{k}"] = round(recall_at_k(relevant, k, total_relevant), 4)
        metrics[f"hit_rate@{k}"] = round(hit_rate(relevant, k), 4)
        metrics[f"ndcg@{k}"] = round(ndcg_at_k(grades, k), 4)
    
    metrics["map"] = round(average_precision(relevant), 4)
    metrics["total_items"] = len(items_sorted)
    metrics["total_relevant"] = total_relevant
    metrics["relevance_ratio"] = round(total_relevant / max(len(items_sorted), 1), 4)
    
    if scores:
        dist = score_distribution_stats(scores)
        for key, val in dist.items():
            metrics[f"score_{key}"] = val
    
    return metrics
