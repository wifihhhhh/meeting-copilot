from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable

from database.models import ActionItemRecord
from services.meeting_insights import normalize_status


@dataclass(frozen=True)
class TaskStatistics:
    total: int
    pending: int
    in_progress: int
    completed: int
    overdue: int
    due_today: int
    upcoming: int
    completion_rate: float


def calculate_task_statistics(
    actions: Iterable[ActionItemRecord],
    *,
    today: date | None = None,
    upcoming_days: int = 3,
) -> TaskStatistics:
    today = today or date.today()
    items = list(actions)
    statuses = [normalize_status(item.status) for item in items]
    completed = sum(status == "已完成" for status in statuses)
    pending = sum(status in {"待办", "延期"} for status in statuses)
    in_progress = sum(status == "进行中" for status in statuses)
    overdue = 0
    due_today = 0
    upcoming = 0

    for item, status in zip(items, statuses):
        if status in {"已完成", "取消"}:
            continue
        deadline = parse_deadline(item.deadline, today=today)
        if deadline is None:
            continue
        if deadline < today:
            overdue += 1
        elif deadline == today:
            due_today += 1
        elif deadline <= today + timedelta(days=max(0, upcoming_days)):
            upcoming += 1

    total = len(items)
    completion_rate = round(completed / total * 100, 1) if total else 0.0
    return TaskStatistics(
        total=total,
        pending=pending,
        in_progress=in_progress,
        completed=completed,
        overdue=overdue,
        due_today=due_today,
        upcoming=upcoming,
        completion_rate=completion_rate,
    )


def filter_action_items(
    actions: Iterable[ActionItemRecord],
    *,
    owner: str = "",
    status: str = "",
    due: str = "全部",
    today: date | None = None,
    upcoming_days: int = 3,
) -> list[ActionItemRecord]:
    today = today or date.today()
    result: list[ActionItemRecord] = []
    for item in actions:
        item_status = normalize_status(item.status)
        deadline = parse_deadline(item.deadline, today=today)
        if owner and item.owner != owner:
            continue
        if status and item_status != status:
            continue
        if due == "逾期" and not (deadline and deadline < today and item_status not in {"已完成", "取消"}):
            continue
        if due == "今天到期" and deadline != today:
            continue
        if due == "未来3天" and not (deadline and today < deadline <= today + timedelta(days=upcoming_days)):
            continue
        if due == "未设置截止时间" and deadline is not None:
            continue
        result.append(item)
    return result


def list_owners(actions: Iterable[ActionItemRecord]) -> list[str]:
    return sorted({item.owner.strip() for item in actions if item.owner.strip()})


def parse_deadline(value: str | None, *, today: date | None = None) -> date | None:
    clean = re.sub(r"\s+", "", str(value or ""))
    if not clean:
        return None
    today = today or date.today()
    normalized = clean.replace("年", "-").replace("月", "-").replace("日", "").replace("/", "-").replace(".", "-")
    for fmt in ("%Y-%m-%d", "%Y-%m"):
        try:
            parsed = datetime.strptime(normalized, fmt).date()
            if fmt == "%Y-%m":
                return parsed.replace(day=1)
            return parsed
        except ValueError:
            continue
    match = re.search(r"(?:(\d{4})-)?(\d{1,2})-(\d{1,2})", normalized)
    if not match:
        return None
    year = int(match.group(1) or today.year)
    try:
        return date(year, int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None
