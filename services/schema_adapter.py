from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from services.meeting_schema import ActionItem, DecisionItem, DiscussionPoint, MeetingMinutes, Topic


@dataclass(frozen=True)
class AdaptedMeeting:
    external_id: str
    source: str
    raw_text: str
    minutes: MeetingMinutes


def adapt_legacy_minutes(
    payload: dict[str, Any],
    *,
    raw_text: str = "",
    source: str = "real_dataset",
) -> AdaptedMeeting:
    """Convert the legacy Chinese-key JSON format into MeetingMinutes."""
    external_id = _clean(payload.get("会议ID")) or "unknown"
    date, time = _split_date_time(_clean(payload.get("会议时间")))

    topics = [Topic(title=item) for item in _string_list(payload.get("核心讨论议题"))]

    budget = _clean(payload.get("预算/费用相关"))
    if budget:
        topics.append(
            Topic(
                title="预算与费用",
                discussion_points=[DiscussionPoint(speaker="", point=budget)],
            )
        )

    risks = _string_list(payload.get("风险与注意事项"))
    if risks:
        topics.append(
            Topic(
                title="风险与注意事项",
                discussion_points=[DiscussionPoint(speaker="", point=item) for item in risks],
            )
        )

    decisions = [
        DecisionItem(owner="", content=item, deadline="", topic="")
        for item in _string_list(payload.get("达成共识/确定方案"))
    ]

    actions: list[ActionItem] = []
    for item in _string_list(payload.get("分工安排")):
        owner, task, deadline = parse_assignment(item)
        actions.append(ActionItem(owner=owner, task=task, deadline=deadline, status="待办"))
    for item in _string_list(payload.get("待解决问题/遗留事项")):
        actions.append(ActionItem(owner="", task=item, deadline="", status="待办"))

    minutes = MeetingMinutes(
        title=_clean(payload.get("会议主题")) or f"会议 {external_id}",
        date=date,
        time=time,
        participants=_string_list(payload.get("参会人员")),
        summary=_clean(payload.get("会议摘要")),
        topics=_dedupe_topics(topics),
        decisions=_dedupe_decisions(decisions),
        action_items=_dedupe_actions(actions),
    )
    return AdaptedMeeting(
        external_id=external_id,
        source=source,
        raw_text=raw_text.strip(),
        minutes=minutes,
    )


def load_legacy_meeting(
    json_path: str | Path,
    *,
    raw_dir: str | Path | None = None,
    source: str = "real_dataset",
) -> AdaptedMeeting:
    json_path = Path(json_path)
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    external_id = _clean(payload.get("会议ID")) or json_path.stem
    raw_text = ""
    if raw_dir is not None:
        raw_text = _load_matching_raw_text(Path(raw_dir), external_id)
    return adapt_legacy_minutes(payload, raw_text=raw_text, source=source)


def parse_assignment(text: str) -> tuple[str, str, str]:
    clean = _clean(text)
    owner_match = re.search(r"负责人\s*[：:]\s*([^，,；;]+)", clean)
    task_match = re.search(r"任务\s*[：:]\s*(.+?)(?=(?:[，,；;]\s*截止(?:时间)?\s*[：:])|$)", clean)
    deadline_match = re.search(r"截止(?:时间)?\s*[：:]\s*(.+)$", clean)

    owner = owner_match.group(1).strip() if owner_match else ""
    task = task_match.group(1).strip() if task_match else clean
    deadline = deadline_match.group(1).strip() if deadline_match else ""
    return owner, task, deadline


def _load_matching_raw_text(raw_dir: Path, external_id: str) -> str:
    matches = sorted(raw_dir.glob(f"{external_id}*.txt"))
    if not matches:
        return ""
    return matches[0].read_text(encoding="utf-8")


def _split_date_time(value: str) -> tuple[str, str]:
    if not value:
        return "", ""
    date_match = re.search(r"\d{4}(?:[-/.年]\d{1,2})(?:[-/.月]\d{1,2})日?", value)
    time_match = re.search(r"\d{1,2}:\d{2}(?:\s*[-~至]\s*\d{1,2}:\d{2})?", value)
    date = date_match.group(0).replace("年", "-").replace("月", "-").replace("日", "") if date_match else value
    return date, time_match.group(0) if time_match else ""


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    return [clean for item in items if (clean := _clean(item))]


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _dedupe_topics(items: list[Topic]) -> list[Topic]:
    result: list[Topic] = []
    seen: set[str] = set()
    for item in items:
        key = item.title.strip()
        if key and key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _dedupe_decisions(items: list[DecisionItem]) -> list[DecisionItem]:
    result: list[DecisionItem] = []
    seen: set[str] = set()
    for item in items:
        key = item.content.strip()
        if key and key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _dedupe_actions(items: list[ActionItem]) -> list[ActionItem]:
    result: list[ActionItem] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        key = (item.owner.strip(), item.task.strip())
        if item.task.strip() and key not in seen:
            seen.add(key)
            result.append(item)
    return result
