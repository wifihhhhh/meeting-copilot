import json

import streamlit as st

from auth_ui import render_user_box, require_login
from config import BASE_DIR
from services.evaluation_service import action_texts, decision_texts, precision_recall_f1
from ui import apply_modern_theme, metric_card, page_header


st.set_page_config(page_title="评估看板", page_icon="MC", layout="wide")
apply_modern_theme()
require_login()
render_user_box()
page_header("效果评估", "上传系统输出和人工标注 JSON，计算 Precision、Recall、F1。", "实验分析")

predicted_file = st.file_uploader("上传系统输出 JSON", type=["json"], key="pred")
gold_file = st.file_uploader("上传人工标注 JSON", type=["json"], key="gold")

if predicted_file and gold_file:
    predicted = json.loads(predicted_file.getvalue().decode("utf-8"))
    gold = json.loads(gold_file.getvalue().decode("utf-8"))

    action_scores = precision_recall_f1(action_texts(predicted), action_texts(gold))
    decision_scores = precision_recall_f1(decision_texts(predicted), decision_texts(gold))

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

st.divider()
st.subheader("内置实验材料")
sample_dir = BASE_DIR / "data" / "samples"
annotation_dir = BASE_DIR / "data" / "annotations"

st.write("样例会议记录：")
sample_files = sorted(sample_dir.glob("*.txt")) if sample_dir.exists() else []
for path in sample_files:
    st.write(f"- `{path.name}`")

st.write("人工标注：")
annotation_files = sorted(annotation_dir.glob("*.json")) if annotation_dir.exists() else []
for path in annotation_files:
    st.write(f"- `{path.name}`")
