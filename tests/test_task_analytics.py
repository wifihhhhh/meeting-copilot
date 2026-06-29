from datetime import date

from database.models import ActionItemRecord
from services.task_analytics import calculate_task_statistics, filter_action_items, parse_deadline


def action(item_id: int, owner: str, deadline: str, status: str) -> ActionItemRecord:
    return ActionItemRecord(
        id=item_id,
        meeting_id=1,
        owner=owner,
        task=f"任务 {item_id}",
        deadline=deadline,
        status=status,
    )


def test_task_statistics_include_overdue_today_and_upcoming():
    today = date(2026, 6, 18)
    items = [
        action(1, "A", "2026-06-17", "待办"),
        action(2, "A", "2026-06-18", "进行中"),
        action(3, "B", "6/20", "待办"),
        action(4, "B", "2026-06-10", "已完成"),
    ]

    stats = calculate_task_statistics(items, today=today)

    assert stats.total == 4
    assert stats.overdue == 1
    assert stats.due_today == 1
    assert stats.upcoming == 1
    assert stats.completed == 1
    assert stats.completion_rate == 25.0


def test_filter_action_items_by_owner_and_due_state():
    today = date(2026, 6, 18)
    items = [
        action(1, "A", "2026-06-17", "待办"),
        action(2, "B", "2026-06-20", "待办"),
    ]

    filtered = filter_action_items(items, owner="A", due="逾期", today=today)

    assert [item.id for item in filtered] == [1]


def test_parse_deadline_supports_common_chinese_formats():
    today = date(2026, 6, 18)
    assert parse_deadline("2026年6月20日", today=today) == date(2026, 6, 20)
    assert parse_deadline("6/21", today=today) == date(2026, 6, 21)
    assert parse_deadline("下周一", today=today) is None
