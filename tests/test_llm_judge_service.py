from services.llm_judge_service import LLMJudgeService, calculate_weighted_score, hard_rules_check
from services.ollama_client import parse_json_block


def test_parse_json_block_tolerates_control_characters_in_model_reason():
    payload = parse_json_block('{"准确性": 5, "理由": "第一行\n第二行"}')
    assert payload["准确性"] == 5


def test_hard_rule_detects_detailed_answer_without_context():
    result = hard_rules_check("这是一个很长的回答。" * 20, "", False)

    assert result is not None
    assert result["忠实性"] == 1


def test_rule_based_judge_returns_weighted_score():
    result = LLMJudgeService().judge(
        question="结论是什么？",
        answer="采用方案 A",
        expected_answer="采用方案 A",
        contexts=["会议决定采用方案 A"],
        use_llm=False,
    )

    assert result["weighted_score"] > 4
    assert result["retrieval_success"] is True


def test_weighted_score_uses_formal_dimensions():
    assert calculate_weighted_score({name: 5 for name in ["忠实性", "准确性", "完整性", "相关性", "简洁性"]}) == 5.0
