import json

import streamlit as st

from auth_ui import render_user_box, require_login
from config import (
    BASE_DIR,
    DEFAULT_EMBEDDING_PROVIDER,
    DEFAULT_MODEL,
    RAG_SIMILARITY_THRESHOLD,
)
from database.repository import MeetingRepository
from services.export_service import ExportService
from services.file_loader import load_text_from_upload
from services.meeting_extractor import MeetingExtractor
from services.minutes_editor import parse_edited_json, to_pretty_json
from services.minutes_formatter import format_minutes
from services.ollama_client import OllamaClient
from services.rag_service import RAGService
from ui import apply_modern_theme, metric_card, page_header, skeleton_loader


st.set_page_config(page_title="生成纪要", page_icon="MC", layout="wide")
apply_modern_theme()
user_id = require_login()
render_user_box()
page_header("生成会议纪要", "输入会议记录，自动抽取议题、发言要点、决议和待办事项。", "当前账号私有")

repo = MeetingRepository()
exporter = ExportService()

st.session_state.setdefault("model", DEFAULT_MODEL)
st.session_state.setdefault("embedding_provider", DEFAULT_EMBEDDING_PROVIDER)
st.session_state.setdefault("similarity_threshold", RAG_SIMILARITY_THRESHOLD)

sample_dir = BASE_DIR / "data" / "samples"
sample_files = sorted(sample_dir.glob("*.txt")) if sample_dir.exists() else []
sample_names = ["不加载样例"] + [path.name for path in sample_files]

with st.expander("生成设置与样例", expanded=True):
    s1, s2, s3, s4 = st.columns([1.15, 0.8, 0.8, 1.35], gap="large")
    with s1:
        model = st.text_input("Ollama 模型", value=st.session_state.get("model", "qwen2.5:1.5b"))
    with s2:
        use_llm = st.toggle("使用 Ollama", value=st.session_state.get("use_llm", True))
    with s3:
        fallback = st.toggle("规则兜底", value=True)
    with s4:
        selected_sample = st.selectbox("载入会议记录", sample_names)
    st.caption("选择样例后会自动填入输入框；也可以直接粘贴自己的会议记录或上传 TXT/Markdown 转写文本。")

st.session_state.model = model
st.session_state.use_llm = use_llm

default_text = ""
if selected_sample != "不加载样例":
    sample_path = next(path for path in sample_files if path.name == selected_sample)
    default_text = sample_path.read_text(encoding="utf-8")

uploaded = st.file_uploader("上传 TXT 或 Markdown 转写文本", type=["txt", "md"])
if uploaded:
    default_text = load_text_from_upload(uploaded)
    st.toast("文件已载入")

if "draft_raw_text" not in st.session_state or default_text:
    st.session_state.draft_raw_text = default_text

left, right = st.columns([1.05, 0.95], gap="large")

with left:
    st.markdown("### 会议记录")
    raw_text = st.text_area(
        "会议记录输入框",
        value=st.session_state.get("draft_raw_text", ""),
        height=430,
        label_visibility="collapsed",
        placeholder="粘贴会议逐字稿、音频转写文本或讨论记录...",
    )
    st.session_state.draft_raw_text = raw_text

    b1, b2 = st.columns([2, 1])
    with b1:
        generate = st.button("生成纪要", type="primary", use_container_width=True)
    with b2:
        if st.button("清空输入", use_container_width=True):
            st.session_state.draft_raw_text = ""
            st.toast("输入已清空")
            st.rerun()

with right:
    st.markdown("### 当前状态")
    current = st.session_state.get("current_minutes")
    m1, m2 = st.columns(2)
    with m1:
        metric_card("识别主题", current.get("title", "-") if current else "-")
    with m2:
        metric_card("会议 ID", str(st.session_state.get("current_meeting_id", "-")))

    if current:
        st.markdown(st.session_state.get("current_markdown", ""))
    else:
        st.info("生成后将在这里显示可读纪要。")

if generate:
    if not raw_text.strip():
        st.warning("请先输入或载入会议记录。")
    else:
        loading = st.empty()
        try:
            loading.markdown(skeleton_loader("AI 正在整理会议脉络"), unsafe_allow_html=True)
            with st.spinner("正在生成结构化纪要..."):
                extractor = MeetingExtractor(OllamaClient(model=model))
                minutes_model = extractor.extract(raw_text, use_llm=use_llm, fallback_to_heuristic=fallback)
                minutes = minutes_model.model_dump()
                markdown = format_minutes(minutes)
                meeting_id = repo.create_meeting(
                    title=minutes.get("title") or "未命名会议",
                    meeting_date=minutes.get("date"),
                    raw_text=raw_text,
                    minutes_json=minutes,
                    minutes_markdown=markdown,
                    user_id=user_id,
                )
                try:
                    RAGService(
                        repository=repo,
                        embedding_provider=st.session_state.get("embedding_provider", "hash"),
                        similarity_threshold=st.session_state.get("similarity_threshold"),
                    ).index_meeting(
                        meeting_id,
                        minutes.get("title") or "未命名会议",
                        minutes.get("date"),
                        markdown,
                        user_id=user_id,
                    )
                except Exception as rag_exc:
                    st.warning(f"纪要已保存，但向量索引暂不可用：{rag_exc}")

                st.session_state.current_meeting_id = meeting_id
                st.session_state.current_minutes = minutes
                st.session_state.current_markdown = markdown
            loading.empty()
            st.toast(f"纪要已保存，会议 ID：{meeting_id}")
            st.rerun()
        except Exception as exc:
            loading.empty()
            st.error(f"生成失败：{exc}")

if "current_minutes" in st.session_state:
    st.divider()
    st.markdown("### 编辑与导出")

    edit_tab, markdown_tab, export_tab = st.tabs(["结构化 JSON", "Markdown 纪要", "导出"])

    with edit_tab:
        edited_json = st.text_area("编辑 JSON", value=to_pretty_json(st.session_state.current_minutes), height=520)
        if st.button("应用 JSON 修改", type="primary"):
            try:
                parsed = parse_edited_json(edited_json)
                markdown = format_minutes(parsed)
                st.session_state.current_minutes = parsed
                st.session_state.current_markdown = markdown
                if st.session_state.get("current_meeting_id"):
                    repo.update_meeting(st.session_state.current_meeting_id, parsed, markdown, user_id=user_id)
                st.toast("JSON 修改已保存")
                st.rerun()
            except json.JSONDecodeError as exc:
                st.error(f"JSON 格式错误：{exc}")

    with markdown_tab:
        edited_markdown = st.text_area("编辑 Markdown", value=st.session_state.current_markdown, height=520)
        if st.button("应用 Markdown 修改"):
            st.session_state.current_markdown = edited_markdown
            if st.session_state.get("current_meeting_id"):
                repo.update_meeting(
                    st.session_state.current_meeting_id,
                    st.session_state.current_minutes,
                    edited_markdown,
                    user_id=user_id,
                )
            st.toast("Markdown 修改已保存")

    with export_tab:
        title = st.session_state.current_minutes.get("title") or "未命名会议"
        col1, col2, col3 = st.columns(3)
        with col1:
            md_path = exporter.export_markdown(st.session_state.current_markdown, title)
            st.download_button("下载 Markdown", md_path.read_bytes(), file_name=md_path.name, use_container_width=True)
        with col2:
            json_path = exporter.export_json(st.session_state.current_minutes, title)
            st.download_button("下载 JSON", json_path.read_bytes(), file_name=json_path.name, use_container_width=True)
        with col3:
            pdf_path = exporter.export_pdf(st.session_state.current_markdown, title)
            st.download_button("下载 PDF", pdf_path.read_bytes(), file_name=pdf_path.name, use_container_width=True)
