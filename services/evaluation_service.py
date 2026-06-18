from typing import Any


def precision_recall_f1(predicted: list[str], gold: list[str]) -> dict[str, float]:
    pred_set = {item.strip() for item in predicted if item.strip()}
    gold_set = {item.strip() for item in gold if item.strip()}
    true_positive = len(pred_set & gold_set)
    precision = true_positive / len(pred_set) if pred_set else 0.0
    recall = true_positive / len(gold_set) if gold_set else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def action_texts(minutes: dict[str, Any]) -> list[str]:
    return [f"{item.get('owner', '')}:{item.get('task', '')}" for item in minutes.get("action_items", [])]


def decision_texts(minutes: dict[str, Any]) -> list[str]:
    return [str(item.get("content", "")) for item in minutes.get("decisions", [])]
