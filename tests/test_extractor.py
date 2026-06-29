import json

import pytest

from services.meeting_extractor import InvalidMeetingTextError, MeetingExtractor
from services.meeting_schema import MeetingMinutes


def test_heuristic_extractor_returns_pydantic_minutes():
    text = """
    主题：Q3 产品规划讨论
    时间：2024-06-01 14:00-15:30
    参会人：张总、李经理、王工
    张总：确定 7 月启动微服务拆分，由王工出技术方案。
    王工 6/14 前提交微服务拆分技术方案。
    """
    result = MeetingExtractor().extract(text, use_llm=False)
    assert isinstance(result, MeetingMinutes)
    assert result.title == "Q3 产品规划讨论"
    assert "王工" in result.participants
    assert result.decisions
    assert result.action_items


def test_short_input_raises_clear_error():
    with pytest.raises(InvalidMeetingTextError):
        MeetingExtractor().extract("太短", use_llm=False)


def test_llm_json_schema_validation_with_fake_client():
    class FakeClient:
        def generate(self, prompt, temperature=0.2, format_schema=None):
            assert format_schema is not None
            return json.dumps(
                {
                    "title": "技术评审会",
                    "date": "2024-06-15",
                    "time": "10:00-11:00",
                    "participants": ["王工"],
                    "summary": "讨论微服务拆分方案。",
                    "topics": [
                        {
                            "title": "微服务拆分",
                            "discussion_points": [{"speaker": "王工", "point": "建议采用 DDD。"}],
                            "decisions": ["先拆用户服务和订单服务"],
                        }
                    ],
                    "decisions": [
                        {
                            "owner": "王工",
                            "content": "第一期拆分用户服务和订单服务",
                            "deadline": "6/20",
                            "topic": "微服务拆分",
                        }
                    ],
                    "action_items": [
                        {"owner": "王工", "task": "补充服务边界文档", "deadline": "6/20", "status": "待办"}
                    ],
                },
                ensure_ascii=False,
            )

    result = MeetingExtractor(client=FakeClient()).extract("这是一段足够长的会议记录，讨论微服务拆分和后续待办。")
    assert isinstance(result, MeetingMinutes)
    assert result.action_items[0].owner == "王工"
