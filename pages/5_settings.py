import streamlit as st

from auth_ui import render_user_box, require_login
from config import (
    BGE_EMBEDDING_MODEL,
    CHROMA_PATH,
    DATABASE_PATH,
    DEFAULT_EMBEDDING_PROVIDER,
    DEFAULT_MODEL,
    EXPORT_DIR,
    RAG_SIMILARITY_THRESHOLD,
)
from services.embedding_service import EmbeddingError, OllamaEmbeddingFunction
from services.ollama_client import OllamaClient
from ui import apply_modern_theme, bento_card, page_header


st.set_page_config(page_title="系统设置", page_icon="MC", layout="wide")
apply_modern_theme()
require_login()
render_user_box()
page_header("系统设置", "配置模型并检查本地数据路径。", "本地开发版")

left, right = st.columns([0.85, 1.15], gap="large")

with left:
    st.subheader("模型")
    model = st.text_input("Ollama 模型", value=st.session_state.get("model", DEFAULT_MODEL))
    use_llm = st.checkbox("默认使用 Ollama", value=st.session_state.get("use_llm", True))
    embedding_provider = st.selectbox(
        "Embedding Provider",
        ["hash", "bge-m3"],
        index=0 if st.session_state.get("embedding_provider", DEFAULT_EMBEDDING_PROVIDER) == "hash" else 1,
    )
    similarity_threshold = st.slider(
        "RAG 相似度阈值",
        min_value=0.0,
        max_value=1.0,
        value=float(st.session_state.get("similarity_threshold", RAG_SIMILARITY_THRESHOLD)),
        step=0.05,
    )

    st.session_state.model = model
    st.session_state.use_llm = use_llm
    st.session_state.embedding_provider = embedding_provider
    st.session_state.similarity_threshold = similarity_threshold

    if st.button("测试 Ollama 连接", type="primary", use_container_width=True):
        client = OllamaClient(model=model)
        if client.is_available():
            st.toast("Ollama 连接正常")
            st.success("Ollama 连接正常。")
        else:
            st.warning("无法连接 Ollama。系统仍可使用规则兜底模式演示。")

    if st.button("测试 BGE-M3 Embedding", use_container_width=True):
        try:
            vector = OllamaEmbeddingFunction(model=BGE_EMBEDDING_MODEL)(["会议纪要向量测试"])[0]
            st.success(f"BGE-M3 可用，向量维度：{len(vector)}。")
        except EmbeddingError as exc:
            st.warning(f"BGE-M3 不可用：{exc}")

with right:
    bento_card(
        "Runtime",
        "本地运行说明",
        "SQLite 保存账号、会议和评估结果；ChromaDB 保存向量索引；exports 保存导出的 Markdown、JSON、PDF 文件。",
        large=True,
    )

st.subheader("本地路径")
st.code(f"SQLite: {DATABASE_PATH}")
st.code(f"ChromaDB: {CHROMA_PATH}")
st.code(f"Exports: {EXPORT_DIR}")
