import re
from typing import Any


def precision_recall_f1(predicted: list[str], gold: list[str]) -> dict[str, float]:
    pred_set = {item.strip() for item in predicted if item.strip()}
    gold_set = {item.strip() for item in gold if item.strip()}
    true_positive = len(pred_set & gold_set)
    precision = true_positive / len(pred_set) if pred_set else 0.0
    recall = true_positive / len(gold_set) if gold_set else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def fuzzy_precision_recall_f1(
    predicted: list[str],
    gold: list[str],
    *,
    threshold: float = 0.35,
) -> dict[str, Any]:
    predicted = [item.strip() for item in predicted if item.strip()]
    gold = [item.strip() for item in gold if item.strip()]
    if not predicted and not gold:
        return _metric_payload(0, 0, 0, [])

    candidates = [
        (keyword_coverage_similarity(pred_item, gold_item), pred_index, gold_index)
        for pred_index, pred_item in enumerate(predicted)
        for gold_index, gold_item in enumerate(gold)
    ]
    candidates.sort(reverse=True)
    matched_pred: set[int] = set()
    matched_gold: set[int] = set()
    matched_pairs: list[dict[str, Any]] = []
    for similarity, pred_index, gold_index in candidates:
        if similarity < threshold:
            break
        if pred_index in matched_pred or gold_index in matched_gold:
            continue
        matched_pred.add(pred_index)
        matched_gold.add(gold_index)
        matched_pairs.append(
            {
                "predicted": predicted[pred_index],
                "gold": gold[gold_index],
                "similarity": round(similarity, 4),
            }
        )
    return _metric_payload(
        len(matched_pairs),
        len(predicted) - len(matched_pred),
        len(gold) - len(matched_gold),
        matched_pairs,
    )


def keyword_coverage_similarity(predicted: str, gold: str) -> float:
    predicted_keywords = set(_extract_keywords(predicted))
    gold_keywords = set(_extract_keywords(gold))
    if not predicted_keywords or not gold_keywords:
        return 0.0
    intersection = predicted_keywords & gold_keywords
    coverage = len(intersection) / len(gold_keywords)
    union = predicted_keywords | gold_keywords
    jaccard = len(intersection) / len(union) if union else 0.0
    return coverage * 0.7 + jaccard * 0.3


def action_texts(minutes: dict[str, Any]) -> list[str]:
    return [f"{item.get('owner', '')}:{item.get('task', '')}" for item in minutes.get("action_items", [])]


def decision_texts(minutes: dict[str, Any]) -> list[str]:
    return [str(item.get("content", "")) for item in minutes.get("decisions", [])]


def _extract_keywords(text: str) -> list[str]:
    chinese = re.findall(r"[\u4e00-\u9fa5]", str(text))
    numbers = re.findall(r"\d+", str(text))
    latin = re.findall(r"[A-Za-z][A-Za-z0-9_-]+", str(text).lower())
    return chinese + numbers + latin


def _metric_payload(tp: int, fp: int, fn: int, matched_pairs: list[dict[str, Any]]) -> dict[str, Any]:
    precision = tp / (tp + fp) if tp + fp else (1.0 if fn == 0 else 0.0)
    recall = tp / (tp + fn) if tp + fn else (1.0 if fp == 0 else 0.0)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "matched_pairs": matched_pairs,
    }
