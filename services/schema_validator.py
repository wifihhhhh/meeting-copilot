from copy import deepcopy
from typing import Any


DEFAULT_MINUTES: dict[str, Any] = {
    "title": "未命名会议",
    "date": "",
    "time": "",
    "participants": [],
    "summary": "",
    "topics": [],
    "decisions": [],
    "action_items": [],
}


def normalize_minutes(data: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(DEFAULT_MINUTES)
    normalized.update({key: value for key, value in data.items() if value is not None})

    normalized["participants"] = _ensure_list(normalized.get("participants"))
    normalized["topics"] = [_normalize_topic(topic) for topic in _ensure_list(normalized.get("topics"))]
    normalized["decisions"] = [_normalize_decision(item) for item in _ensure_list(normalized.get("decisions"))]
    normalized["action_items"] = [
        _normalize_action(item) for item in _ensure_list(normalized.get("action_items"))
    ]
    return normalized


def _ensure_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _normalize_topic(topic: Any) -> dict[str, Any]:
    if not isinstance(topic, dict):
        return {"title": str(topic), "discussion_points": [], "decisions": []}
    return {
        "title": str(topic.get("title") or "未命名议题"),
        "discussion_points": _ensure_list(topic.get("discussion_points")),
        "decisions": _ensure_list(topic.get("decisions")),
    }


def _normalize_decision(item: Any) -> dict[str, str]:
    if not isinstance(item, dict):
        return {"owner": "", "content": str(item), "deadline": "", "topic": ""}
    return {
        "owner": str(item.get("owner") or ""),
        "content": str(item.get("content") or item.get("task") or ""),
        "deadline": str(item.get("deadline") or ""),
        "topic": str(item.get("topic") or ""),
    }


def _normalize_action(item: Any) -> dict[str, str]:
    if not isinstance(item, dict):
        return {"owner": "", "task": str(item), "deadline": "", "status": "待办"}
    return {
        "owner": str(item.get("owner") or ""),
        "task": str(item.get("task") or item.get("content") or ""),
        "deadline": str(item.get("deadline") or ""),
        "status": str(item.get("status") or "待办"),
    }
