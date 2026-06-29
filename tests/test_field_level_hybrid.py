from services.meeting_extractor import MeetingExtractor
from services.meeting_schema import DecisionItem, MeetingMinutes


def test_field_level_hybrid_keeps_llm_actions_and_prefers_rule_decisions():
    llm_minutes = MeetingMinutes.model_validate(
        {
            "title": "Project review",
            "decisions": [{"content": "LLM decision"}],
            "action_items": [{"owner": "Alice", "task": "Submit proposal"}],
        }
    )
    extractor = MeetingExtractor()
    extractor._find_decisions = lambda _text: [DecisionItem(content="Rule decision")]

    result = extractor._merge_field_level("A sufficiently long meeting transcript", llm_minutes)

    assert result.decisions[0].content == "Rule decision"
    assert result.action_items[0].task == "Submit proposal"


def test_field_level_hybrid_retains_llm_decisions_when_rules_find_nothing():
    llm_minutes = MeetingMinutes.model_validate(
        {"title": "Project review", "decisions": [{"content": "LLM decision"}]}
    )
    extractor = MeetingExtractor()
    extractor._find_decisions = lambda _text: []

    result = extractor._merge_field_level("A sufficiently long meeting transcript", llm_minutes)

    assert result is llm_minutes
