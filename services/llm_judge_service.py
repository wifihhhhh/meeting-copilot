from __future__ import annotations

from typing import Any

from services.ollama_client import OllamaClient, parse_json_block


SCORE_DIMENSIONS = {
    "忠实性": 0.25,
    "准确性": 0.30,
    "完整性": 0.20,
    "相关性": 0.15,
    "简洁性": 0.10,
}


class LLMJudgeService:
    def __init__(self, client: OllamaClient | None = None) -> None:
        self.client = client or OllamaClient()

    def judge(
        self,
        *,
        question: str,
        answer: str,
        expected_answer: str = "",
        contexts: list[str] | None = None,
        use_llm: bool = True,
    ) -> dict[str, Any]:
        contexts = contexts or []
        retrieval_success = bool(contexts)
        hard_result = hard_rules_check(answer, expected_answer, retrieval_success)
        if hard_result is not None:
            return _with_weighted_score(hard_result, retrieval_success, True)
        if not use_llm:
            result = heuristic_scores(answer, expected_answer, retrieval_success)
            return _with_weighted_score(result, retrieval_success, False)

        prompt = build_judge_prompt(question, answer, expected_answer, contexts)
        raw = self.client.generate(prompt, temperature=0.0)
        result = parse_json_block(raw)
        normalized = normalize_scores(result)
        return _with_weighted_score(normalized, retrieval_success, False)


def build_judge_prompt(question: str, answer: str, expected_answer: str, contexts: list[str]) -> str:
    context_text = "\n\n---\n\n".join(contexts) if contexts else "未检索到上下文"
    return f"""你是严格的 RAG 评估专家。请根据检索上下文评价系统回答。

用户问题：{question}
参考答案：{expected_answer or '未提供'}
检索上下文：
{context_text[:4000]}

系统回答：
{answer}

请从忠实性、准确性、完整性、相关性、简洁性五个维度分别给 1-5 分。
只输出 JSON：
{{"忠实性": 1, "准确性": 1, "完整性": 1, "相关性": 1, "简洁性": 1, "理由": "简短理由"}}
"""


def hard_rules_check(answer: str, expected_answer: str, retrieval_success: bool) -> dict[str, Any] | None:
    if not retrieval_success and len(answer) > 100:
        return {
            "忠实性": 1,
            "准确性": 2,
            "完整性": 2,
            "相关性": 2,
            "简洁性": 2,
            "理由": "检索失败但回答包含大量细节，存在幻觉风险。",
        }
    uncertain_words = ["通常", "一般", "可能", "大概", "或许"]
    if not retrieval_success and any(word in answer for word in uncertain_words):
        return {
            "忠实性": 1,
            "准确性": 2,
            "完整性": 2,
            "相关性": 2,
            "简洁性": 2,
            "理由": "检索失败且回答包含推测性措辞。",
        }
    return None


def heuristic_scores(answer: str, expected_answer: str, retrieval_success: bool) -> dict[str, Any]:
    expected_hit = bool(expected_answer and expected_answer in answer)
    base = 5 if expected_hit else 3 if answer.strip() else 1
    return {
        "忠实性": 4 if retrieval_success else 1,
        "准确性": base,
        "完整性": base,
        "相关性": base,
        "简洁性": 4 if len(answer) <= 500 else 3,
        "理由": "未调用 LLM，使用可复现的规则基线评分。",
    }


def normalize_scores(payload: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for dimension in SCORE_DIMENSIONS:
        value = payload.get(dimension, 1)
        try:
            score = float(value)
        except (TypeError, ValueError):
            score = 1.0
        result[dimension] = max(1.0, min(5.0, score))
    result["理由"] = str(payload.get("理由") or "模型未提供理由。")
    return result


def calculate_weighted_score(scores: dict[str, Any]) -> float:
    return round(sum(float(scores.get(name, 1)) * weight for name, weight in SCORE_DIMENSIONS.items()), 2)


def _with_weighted_score(
    scores: dict[str, Any],
    retrieval_success: bool,
    hard_rule_triggered: bool,
) -> dict[str, Any]:
    result = dict(scores)
    result["weighted_score"] = calculate_weighted_score(result)
    result["retrieval_success"] = retrieval_success
    result["hard_rule_triggered"] = hard_rule_triggered
    return result
