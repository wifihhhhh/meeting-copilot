from services.minutes_formatter import format_minutes


def test_format_minutes_contains_action_items():
    markdown = format_minutes(
        {
            "title": "测试会议",
            "date": "2024-06-01",
            "time": "10:00",
            "participants": ["张三"],
            "summary": "讨论测试。",
            "topics": [{"title": "议题", "discussion_points": ["要点"], "decisions": []}],
            "decisions": [],
            "action_items": [{"owner": "张三", "task": "完成测试", "deadline": "6/7", "status": "待办"}],
        }
    )
    assert "# 会议纪要" in markdown
    lines = markdown.splitlines()
    assert lines[2].endswith("  ")
    assert lines[3].endswith("  ")
    assert "张三 -> 完成测试" in markdown
