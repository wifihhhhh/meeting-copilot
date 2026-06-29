import csv
import json

import streamlit as st

from auth_ui import render_user_box, require_login
from config import BASE_DIR, DEFAULT_MODEL
from database.repository import MeetingRepository
from services.evaluation_service import (
    action_texts,
    decision_texts,
    fuzzy_precision_recall_f1,
    precision_recall_f1,
)
from services.llm_judge_service import LLMJudgeService
from services.ollama_client import OllamaClient
from ui import apply_modern_theme, metric_card, page_header


st.set_page_config(page_title="评估看板", page_icon="MC", layout="wide")
apply_modern_theme()
user_id = require_login()
render_user_box()
page_header("效果评估", "对比系统输出与人工标注，并使用 LLM-as-Judge 评估 RAG 回答质量。", "实验分析")

repo = MeetingRepository()
extract_tab, judge_tab, experiment_tab, history_tab = st.tabs(["抽取评估", "RAG Judge", "正式对比实验", "历史结果"])

with extract_tab:
    settings_left, settings_right = st.columns(2)
    with settings_left:
        match_mode = st.selectbox("匹配方式", ["模糊匹配", "严格匹配"])
    with settings_right:
        fuzzy_threshold = st.slider(
            "模糊匹配阈值",
            min_value=0.0,
            max_value=1.0,
            value=0.35,
            step=0.05,
            disabled=match_mode != "模糊匹配",
        )

    predicted_file = st.file_uploader("上传系统输出 JSON", type=["json"], key="pred")
    gold_file = st.file_uploader("上传人工标注 JSON", type=["json"], key="gold")

    if predicted_file and gold_file:
        try:
            predicted = json.loads(predicted_file.getvalue().decode("utf-8"))
            gold = json.loads(gold_file.getvalue().decode("utf-8"))
            scorer = (
                (lambda predicted_items, gold_items: fuzzy_precision_recall_f1(
                    predicted_items,
                    gold_items,
                    threshold=fuzzy_threshold,
                ))
                if match_mode == "模糊匹配"
                else precision_recall_f1
            )
            action_scores = scorer(action_texts(predicted), action_texts(gold))
            decision_scores = scorer(decision_texts(predicted), decision_texts(gold))

            c1, c2, c3 = st.columns(3)
            with c1:
                metric_card("Action F1", f"{action_scores['f1']:.2f}")
            with c2:
                metric_card("Action Precision", f"{action_scores['precision']:.2f}")
            with c3:
                metric_card("Action Recall", f"{action_scores['recall']:.2f}")

            c4, c5, c6 = st.columns(3)
            with c4:
                metric_card("Decision F1", f"{decision_scores['f1']:.2f}")
            with c5:
                metric_card("Decision Precision", f"{decision_scores['precision']:.2f}")
            with c6:
                metric_card("Decision Recall", f"{decision_scores['recall']:.2f}")

            if match_mode == "模糊匹配":
                with st.expander("查看模糊匹配明细"):
                    st.markdown("**Action Items**")
                    st.json(action_scores.get("matched_pairs", []))
                    st.markdown("**Decisions**")
                    st.json(decision_scores.get("matched_pairs", []))

            if st.button("保存抽取评估结果", type="primary"):
                repo.save_evaluation_result(
                    metric_name=f"extraction_{'fuzzy' if match_mode == '模糊匹配' else 'strict'}",
                    user_id=user_id,
                    precision=(action_scores["precision"] + decision_scores["precision"]) / 2,
                    recall=(action_scores["recall"] + decision_scores["recall"]) / 2,
                    f1=(action_scores["f1"] + decision_scores["f1"]) / 2,
                    payload={
                        "threshold": fuzzy_threshold if match_mode == "模糊匹配" else None,
                        "action_scores": action_scores,
                        "decision_scores": decision_scores,
                    },
                )
                st.toast("抽取评估结果已保存")
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            st.error(f"JSON 文件读取失败：{exc}")

with judge_tab:
    j1, j2 = st.columns([1.0, 1.0])
    with j1:
        judge_model = st.text_input("Judge 模型", value=st.session_state.get("model", DEFAULT_MODEL))
    with j2:
        use_judge_llm = st.toggle("使用 Ollama Judge", value=True)

    judge_question = st.text_input("测试问题", placeholder="例如：上次关于微服务拆分的结论是什么？")
    judge_answer = st.text_area("系统回答", height=150)
    expected_answer = st.text_area("参考答案（可选）", height=100)
    retrieved_context = st.text_area("检索上下文（多个片段可用空行分隔）", height=180)

    if st.button("运行 RAG Judge", type="primary", use_container_width=True):
        if not judge_question.strip() or not judge_answer.strip():
            st.warning("请填写测试问题和系统回答。")
        else:
            try:
                contexts = [item.strip() for item in retrieved_context.split("\n\n") if item.strip()]
                result = LLMJudgeService(OllamaClient(model=judge_model)).judge(
                    question=judge_question,
                    answer=judge_answer,
                    expected_answer=expected_answer,
                    contexts=contexts,
                    use_llm=use_judge_llm,
                )
                st.session_state.last_judge_result = result
                repo.save_evaluation_result(
                    metric_name="rag_llm_judge" if use_judge_llm else "rag_rule_judge",
                    user_id=user_id,
                    score=float(result["weighted_score"]),
                    notes=str(result.get("理由") or ""),
                    payload={
                        "question": judge_question,
                        "answer": judge_answer,
                        "expected_answer": expected_answer,
                        "contexts": contexts,
                        "result": result,
                    },
                )
                st.toast("RAG 评估完成并已保存")
            except Exception as exc:
                st.error(f"RAG Judge 失败：{exc}")

    judge_result = st.session_state.get("last_judge_result")
    if judge_result:
        metric_card("加权总分", f"{judge_result['weighted_score']:.2f} / 5")
        st.json(judge_result)

with experiment_tab:
    experiment_dir = BASE_DIR / "data" / "evaluation" / "course_final"
    retrieval_summary_path = experiment_dir / "retrieval_summary.csv"
    answer_summary_path = experiment_dir / "answer_summary.csv"
    extraction_summary_path = experiment_dir / "extraction_summary.csv"
    report_path = experiment_dir / "experiment_report.md"
    st.caption("复现原实验并加入课程指南要求的Chunk消融、无RAG基线、20题Judge和失败案例分析。")
    if not retrieval_summary_path.exists():
        st.info("正式实验尚未生成。运行：python -m scripts.run_course_experiments --with-llm")
    else:
        with retrieval_summary_path.open(encoding="utf-8-sig", newline="") as handle:
            retrieval_rows = list(csv.DictReader(handle))
        st.markdown("#### 检索实验")
        st.dataframe(retrieval_rows, use_container_width=True, hide_index=True)
        retrieval_chart = experiment_dir / "retrieval_comparison.png"
        if retrieval_chart.exists():
            st.image(str(retrieval_chart), caption="Recall@K 与 MRR 对比", use_container_width=True)

        if answer_summary_path.exists():
            with answer_summary_path.open(encoding="utf-8-sig", newline="") as handle:
                answer_rows = list(csv.DictReader(handle))
            st.markdown("#### 端到端问答与 LLM-as-Judge")
            st.dataframe(answer_rows, use_container_width=True, hide_index=True)
            answer_chart = experiment_dir / "answer_quality_comparison.png"
            if answer_chart.exists():
                st.image(str(answer_chart), caption="问答质量与95%置信区间", use_container_width=True)

        if extraction_summary_path.exists():
            with extraction_summary_path.open(encoding="utf-8-sig", newline="") as handle:
                extraction_rows = list(csv.DictReader(handle))
            st.markdown("#### 结构化抽取实验")
            st.dataframe(extraction_rows, use_container_width=True, hide_index=True)

        if report_path.exists():
            st.download_button(
                "下载正式实验报告",
                report_path.read_bytes(),
                file_name="course_experiment_report.md",
                use_container_width=True,
            )

with history_tab:
    results = repo.list_evaluation_results(user_id=user_id)
    if not results:
        st.info("当前账号还没有保存评估结果。")
    else:
        st.dataframe(
            [
                {
                    "时间": item.created_at,
                    "指标": item.metric_name,
                    "Precision": item.precision,
                    "Recall": item.recall,
                    "F1": item.f1,
                    "Score": item.score,
                    "备注": item.notes,
                }
                for item in results
            ],
            use_container_width=True,
            hide_index=True,
        )

st.divider()
st.subheader("内置实验材料")
sample_dir = BASE_DIR / "data" / "samples"
annotation_dir = BASE_DIR / "data" / "annotations"
real_data_dir = BASE_DIR / "data" / "processed"
st.caption(
    f"模拟样例：{len(list(sample_dir.glob('*.txt')))} 份 · "
    f"人工标注：{len(list(annotation_dir.glob('*.json')))} 份 · "
    f"真实结构化会议：{len(list(real_data_dir.glob('M*.json')))} 份"
)
