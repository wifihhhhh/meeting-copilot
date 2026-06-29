from pathlib import Path

from services.schema_adapter import adapt_legacy_minutes, load_legacy_meeting, parse_assignment


def test_adapt_legacy_minutes_preserves_decisions_actions_and_risks():
    adapted = adapt_legacy_minutes(
        {
            "会议ID": "M0001",
            "会议主题": "产品评审",
            "会议时间": "2026-06-18 14:00-15:00",
            "参会人员": ["A", "B", "A"],
            "核心讨论议题": ["排期", "风险"],
            "达成共识/确定方案": ["六月完成第一期"],
            "待解决问题/遗留事项": ["确认测试资源"],
            "分工安排": ["负责人：A，任务：完成 PRD，截止时间：6月20日"],
            "预算/费用相关": "预算一万元",
            "风险与注意事项": ["测试时间不足"],
            "会议摘要": "完成一期方案评审。",
        },
        raw_text="原始会议文本",
    )

    assert adapted.external_id == "M0001"
    assert adapted.minutes.title == "产品评审"
    assert adapted.minutes.date == "2026-06-18"
    assert adapted.minutes.time == "14:00-15:00"
    assert adapted.minutes.participants == ["A", "B"]
    assert adapted.minutes.decisions[0].content == "六月完成第一期"
    assert any(item.owner == "A" and item.task == "完成 PRD" for item in adapted.minutes.action_items)
    assert any(item.task == "确认测试资源" for item in adapted.minutes.action_items)
    assert any(topic.title == "风险与注意事项" for topic in adapted.minutes.topics)


def test_parse_assignment_without_structured_prefix_keeps_content():
    assert parse_assignment("继续确认客户需求") == ("", "继续确认客户需求", "")


def test_all_real_dataset_json_files_adapt_to_meeting_minutes():
    root = Path(__file__).resolve().parents[1]
    json_files = sorted((root / "data" / "processed").glob("M*.json"))

    assert len(json_files) == 36
    for json_path in json_files:
        adapted = load_legacy_meeting(json_path, raw_dir=root / "data" / "raw")
        assert adapted.external_id.startswith("M")
        assert adapted.minutes.title
        assert adapted.raw_text
