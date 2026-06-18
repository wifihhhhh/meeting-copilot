import json
import csv
import re
import requests
from typing import Dict, List, Any

# ===================== API 配置 =====================
DEEPSEEK_API_KEY = "sk-97cbf750d9bc4cd1bdf6c13bf31b2726"  # 你的 API Key
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
JUDGE_MODEL = "deepseek-chat"  # 或 "deepseek-reasoner" 用于更严格评判


# 评分维度及权重（新增忠实性，降低准确性权重）
SCORE_DIMENSIONS = {
    "忠实性": 0.25,   # NEW: 是否基于检索文档，有无幻觉
    "准确性": 0.30,   # 回答是否正确
    "完整性": 0.20,   # 是否完整回答
    "相关性": 0.15,   # 是否与问题相关
    "简洁性": 0.10,   # 是否简洁
}


# ===================== 评分 Prompt（增强版）====================
def get_judge_prompt(question: str, system_answer: str, expected_answer: str = None, 
                     retrieved_context: str = None, retrieval_success: bool = True) -> str:
    """生成评分 prompt（增强版）"""
    
    expected_section = f"\n【标准答案参考】\n{expected_answer}\n" if expected_answer else ""
    
    # 如果有检索上下文，加入Prompt
    context_section = ""
    if retrieved_context:
        context_section = f"\n【系统检索到的参考文档】\n{retrieved_context[:800]}\n"
    
    # 检索失败警告
    retrieval_warning = ""
    if not retrieval_success:
        retrieval_warning = """
⚠️ 重要提示：系统未检索到相关文档（检索失败），上述"系统回答"可能是模型自行编造的。
如果回答中包含检索文档以外的信息，或回答看起来像"通用知识"而非基于具体会议内容，请给忠实性打1分。
"""
    
    return f"""你是一个专业的 RAG 系统评估专家。请严格对以下系统回答进行评分。

【用户问题】
{question}
{expected_section}
{context_section}
【系统回答】
{system_answer}
{retrieval_warning}

【评分标准】
请从以下五个维度分别打分（1-5分，5分为最好）：

1. **忠实性（Faithfulness）**：回答是否严格基于检索到的文档？有无编造/幻觉？
   - 5分：完全基于文档，无任何编造
   - 4分：基本基于文档，有少量推测
   - 3分：部分基于文档，部分编造
   - 2分：大量编造，很少基于文档
   - 1分：完全编造，与文档无关（尤其是检索失败时）

2. **准确性（Accuracy）**：回答的事实是否正确？
   - 5分：完全正确
   - 4分：基本正确，有小瑕疵
   - 3分：部分正确，有明显错误
   - 2分：大部分错误
   - 1分：完全错误

3. **完整性（Completeness）**：是否完整回答了用户问题？
   - 5分：完整覆盖所有要点
   - 3分：覆盖部分要点
   - 1分：完全没有回答

4. **相关性（Relevance）**：回答是否与问题相关？
   - 5分：高度相关
   - 3分：部分相关
   - 1分：完全不相关

5. **简洁性（Conciseness）**：回答是否简洁直接？
   - 5分：非常简洁
   - 3分：一般，有废话
   - 1分：非常冗长

【输出格式】
请只输出 JSON，不要其他内容：
{{
    "忠实性": 分数,
    "准确性": 分数,
    "完整性": 分数,
    "相关性": 分数,
    "简洁性": 分数,
    "总分": 平均分,
    "理由": "简短理由，特别说明是否有幻觉或编造"
}}"""


# ===================== 评分函数（增强版）====================
def judge_answer(question: str, system_answer: str, expected_answer: str = None,
                 retrieved_context: str = None, retrieval_success: bool = True) -> Dict[str, Any]:
    
    prompt = get_judge_prompt(question, system_answer, expected_answer, 
                              retrieved_context, retrieval_success)
    
    try:
        # 删除 ollama.chat 调用，改为 requests.post
        response = requests.post(
            DEEPSEEK_API_URL,
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": JUDGE_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "max_tokens": 800
            },
            timeout=60
        )
        response.raise_for_status()
        result_text = response.json()["choices"][0]["message"]["content"].strip()
        
        # 后续 JSON 解析逻辑不变...
        
        # ========== 修复1：增强JSON提取逻辑 ==========
        # 方法1：移除非JSON内容，只保留{}包裹的部分
        json_match = re.search(r'\{[\s\S]*\}', result_text)  # 把*?改为*，匹配完整JSON
        if json_match:
            try:
                result = json.loads(json_match.group(0))
            except json.JSONDecodeError:
                # JSON格式错误，尝试清理后解析
                clean_json = json_match.group(0).replace("'", "\"")  # 单引号改双引号
                clean_json = re.sub(r',\s*}', '}', clean_json)  # 移除末尾多余逗号
                result = json.loads(clean_json)
        else:
            # 完全匹配不到JSON，返回保底评分（基于回答正确性）
            result = {
                "忠实性": 5 if retrieval_success else 1,
                "准确性": 5 if expected_answer in system_answer else 1,
                "完整性": 5 if expected_answer in system_answer else 1,
                "相关性": 5,
                "简洁性": 5,
                "总分": 5,
                "理由": "JSON解析失败，基于关键词匹配保底评分"
            }
        
        # ========== 修复2：强制修正逻辑保留 ==========
        if not retrieval_success and result.get("忠实性", 5) > 2:
            result["忠实性"] = 2
            result["理由"] = (result.get("理由", "") + 
                              " [强制修正：检索失败，回答应为编造]").strip()
        
        return result
    
    except Exception as e:
        # ========== 修复3：异常时返回保底评分 ==========
        # 回答包含预期答案则保底高分，否则低分
        is_correct = expected_answer in system_answer if expected_answer else False
        base_score = 5 if is_correct else 1
        return {
            "error": str(e), 
            "忠实性": base_score if retrieval_success else 1,
            "准确性": base_score, 
            "完整性": base_score, 
            "相关性": base_score, 
            "简洁性": base_score, 
            "总分": base_score,
            "理由": f"调用LLM失败：{str(e)}，基于关键词匹配保底评分"
        }

def calculate_weighted_score(scores: Dict[str, float]) -> float:
    """计算加权总分"""
    total = 0
    for dim, weight in SCORE_DIMENSIONS.items():
        if dim in scores and isinstance(scores[dim], (int, float)):
            total += scores[dim] * weight
    return round(total, 2)


# ===================== 硬规则：检测明显幻觉 =====================
def hard_rules_check(system_answer: str, expected_answer: str = None, 
                     retrieval_success: bool = True) -> Dict[str, Any]:
    """硬规则快速检测，绕过LLM评分"""
    
    # 规则1：检索失败 + 回答很长很详细 = 大概率幻觉
    if not retrieval_success and len(system_answer) > 100:
        return {
            "忠实性": 1,
            "准确性": 2,
            "完整性": 3,
            "相关性": 2,
            "简洁性": 2,
            "总分": 1.8,
            "理由": "[硬规则触发] 检索失败但回答详细，判定为模型幻觉编造",
            "hard_rule_triggered": True
        }
    
    # 规则2：回答包含"通常""一般""可能"等模糊词，且检索失败
    fuzzy_words = ["通常", "一般", "可能", "大概", "或许", "如果"]
    if not retrieval_success and any(w in system_answer for w in fuzzy_words):
        return {
            "忠实性": 1,
            "准确性": 2,
            "完整性": 2,
            "相关性": 2,
            "简洁性": 2,
            "总分": 1.7,
            "理由": "[硬规则触发] 检索失败且回答含推测性词汇，判定为幻觉",
            "hard_rule_triggered": True
        }
    
    # 规则3：预期答案存在但回答中完全没提到关键词
    if expected_answer:
        expected_keywords = set(expected_answer.replace("，", " ").replace("、", " ").split())
        answer_keywords = set(system_answer.replace("，", " ").replace("、", " ").split())
        # 简单检查：预期答案中的关键词在回答中出现的比例
        overlap = expected_keywords & answer_keywords
        if len(expected_keywords) > 0 and len(overlap) / len(expected_keywords) < 0.3:
            # 可能是答非所问
            pass  # 不直接触发硬规则，让LLM判断
    
    return None  # 没有触发硬规则


# ===================== 综合评分（LLM + 硬规则）====================
def judge_answer_comprehensive(question: str, system_answer: str, 
                                expected_answer: str = None,
                                retrieved_context: str = None, 
                                retrieval_success: bool = True) -> Dict[str, Any]:
    """综合评分：先过硬规则，再用LLM"""
    
    # 第一步：硬规则快速检测
    hard_result = hard_rules_check(system_answer, expected_answer, retrieval_success)
    if hard_result:
        return hard_result
    
    # 第二步：LLM评分
    return judge_answer(question, system_answer, expected_answer, 
                        retrieved_context, retrieval_success)


# ===================== 评估 RAG 的包装函数 =====================
def evaluate_rag_answer(rag_result: Dict[str, Any], expected_answer: str = None) -> Dict[str, Any]:
    """直接评估 RAG 返回的结果"""
    query = rag_result.get("query", "")
    answer = rag_result.get("answer", "")
    context = rag_result.get("context", "")
    sources = rag_result.get("sources", [])
    
    # 判断检索是否成功：有来源且上下文不是"未找到"
    retrieval_success = len(sources) > 0 and "未找到" not in context
    
    # 综合评分
    scores = judge_answer_comprehensive(
        question=query,
        system_answer=answer,
        expected_answer=expected_answer,
        retrieved_context=context,
        retrieval_success=retrieval_success
    )
    
    weighted = calculate_weighted_score(scores)
    
    return {
        "query": query,
        "answer": answer,
        "expected": expected_answer,
        "retrieval_success": retrieval_success,
        "scores": scores,
        "weighted_score": weighted
    }


# ===================== 批量评估 =====================
def batch_evaluate(rag_system, test_cases: List[Dict]) -> List[Dict]:
    """批量评估 RAG 系统"""
    results = []
    
    print("=" * 60)
    print(" RAG 质量评估（修复版）")
    print("=" * 60)
    
    for i, test in enumerate(test_cases, 1):
        question = test["question"]
        expected = test.get("expected", "")
        
        print(f"\n[{i}/{len(test_cases)}] {question}")
        
        # 调用 RAG
        rag_result = rag_system.ask(question)
        
        # 评估
        eval_result = evaluate_rag_answer(rag_result, expected)
        
        # 打印
        rs = "✅检索成功" if eval_result["retrieval_success"] else "❌检索失败"
        print(f"   {rs} | 加权分: {eval_result['weighted_score']:.2f}/5")
        print(f"   回答: {eval_result['answer'][:80]}...")
        print(f"   理由: {eval_result['scores'].get('理由', 'N/A')[:60]}")
        
        results.append(eval_result)
    
    # 汇总
    print(f"\n{'='*60}")
    print(" 汇总")
    print(f"{'='*60}")
    
    success_cases = [r for r in results if r["retrieval_success"]]
    fail_cases = [r for r in results if not r["retrieval_success"]]
    
    avg_all = sum(r["weighted_score"] for r in results) / len(results)
    print(f"总体平均分: {avg_all:.2f}/5")
    print(f"检索成功: {len(success_cases)} 次, 检索失败: {len(fail_cases)} 次")
    
    if success_cases:
        avg_success = sum(r["weighted_score"] for r in success_cases) / len(success_cases)
        print(f"检索成功时的平均分: {avg_success:.2f}/5")
    if fail_cases:
        avg_fail = sum(r["weighted_score"] for r in fail_cases) / len(fail_cases)
        print(f"检索失败时的平均分: {avg_fail:.2f}/5")
    
    return results


# ===================== 保存结果 =====================
def save_eval_results(results: List[Dict], filename: str = "rag_eval_results.csv"):
    """保存评估结果"""
    with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow([
            '问题', '预期答案', '系统回答', '检索成功', 
            '忠实性', '准确性', '完整性', '相关性', '简洁性',
            '加权总分', '理由'
        ])
        
        for r in results:
            s = r["scores"]
            writer.writerow([
                r['query'],
                r.get('expected', ''),
                r['answer'],
                '是' if r['retrieval_success'] else '否',
                s.get('忠实性', 0),
                s.get('准确性', 0),
                s.get('完整性', 0),
                s.get('相关性', 0),
                s.get('简洁性', 0),
                r['weighted_score'],
                s.get('理由', '')
            ])
    
    print(f"\n💾 结果已保存到 {filename}")


# ===================== 主函数 =====================
def main():
    print("这是 llm_judge.py 修复版")
    print("用法: from llm_judge import batch_evaluate, save_eval_results")


if __name__ == "__main__":
    main()