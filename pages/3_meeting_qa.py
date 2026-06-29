import streamlit as st

from auth_ui import render_user_box, require_login
from config import (
    DEFAULT_EMBEDDING_PROVIDER,
    DEFAULT_MODEL,
    RAG_SIMILARITY_THRESHOLD,
)
from database.repository import MeetingRepository
from services.meeting_rag import MeetingRAG, VectorStoreUnavailableError
from services.ollama_client import OllamaClient
from ui import apply_modern_theme, metric_card, page_header, skeleton_loader


st.set_page_config(page_title="RAG 问答", page_icon="MC", layout="wide")
apply_modern_theme()
user_id = require_login()
render_user_box()
page_header("RAG 跨会议问答", "从当前账号的历史会议纪要中检索证据，并生成带来源的回答。", "私有知识库")

repo = MeetingRepository()

st.session_state.setdefault("model", DEFAULT_MODEL)
st.session_state.setdefault("embedding_provider", DEFAULT_EMBEDDING_PROVIDER)
st.session_state.setdefault("similarity_threshold", RAG_SIMILARITY_THRESHOLD)

meetings = repo.list_meetings(user_id=user_id)
meeting_options = {"全部会议": None}
meeting_options.update({f"#{item.id} {item.title}": item.id for item in meetings})

with st.expander("问答设置", expanded=True):
    q1, q2, q3, q4 = st.columns([1.15, 0.9, 0.9, 1.45], gap="large")
    with q1:
        model = st.text_input("Ollama 模型", value=st.session_state.get("model", "qwen2.5:1.5b"))
    with q2:
        use_llm = st.toggle("使用 Ollama", value=st.session_state.get("use_llm", True))
    with q3:
        top_k = st.slider("检索 Top-K", min_value=1, max_value=10, value=5)
    with q4:
        selected_meeting = st.selectbox("限定会议范围", list(meeting_options.keys()))
    e1, e2, e3 = st.columns([1.0, 1.0, 1.4], gap="large")
    with e1:
        embedding_provider = st.selectbox(
            "Embedding",
            ["hash", "bge-m3"],
            index=0 if st.session_state.get("embedding_provider", "hash") == "hash" else 1,
        )
    with e2:
        use_threshold = st.toggle(
            "相似度阈值",
            value=st.session_state.get("use_similarity_threshold", embedding_provider == "bge-m3"),
        )
    with e3:
        similarity_threshold = st.slider(
            "最低相似度",
            min_value=0.0,
            max_value=1.0,
            value=float(st.session_state.get("similarity_threshold", 0.30)),
            step=0.05,
            disabled=not use_threshold,
        )
    st.caption("RAG 会检索当前账号的私有会议和系统共享只读语料；BGE-M3 需先执行 ollama pull bge-m3。")

selected_meeting_id = meeting_options[selected_meeting]
st.session_state.model = model
st.session_state.use_llm = use_llm
st.session_state.embedding_provider = embedding_provider
st.session_state.use_similarity_threshold = use_threshold
st.session_state.similarity_threshold = similarity_threshold

actions = repo.list_action_items(user_id=user_id)
decisions = repo.list_decisions(user_id=user_id)

m1, m2, m3 = st.columns(3)
with m1:
    metric_card("可检索会议", str(len(meetings)))
with m2:
    metric_card("待办语料", str(len(actions)))
with m3:
    metric_card("决议语料", str(len(decisions)))

st.divider()

question = st.text_input(
    "输入问题",
    placeholder="例如：上次关于微服务拆分的结论是什么？王工后续有没有汇报方案？",
    label_visibility="collapsed",
)
ask = st.button("开始问答", type="primary", use_container_width=True)

if ask and question:
    loading = st.empty()
    try:
        rag = MeetingRAG(
            repository=repo,
            client=OllamaClient(model=model),
            embedding_provider=embedding_provider,
            similarity_threshold=similarity_threshold if use_threshold else None,
        )
        loading.markdown(skeleton_loader("正在检索历史会议"), unsafe_allow_html=True)
        with st.spinner("正在检索我的历史会议并生成回答..."):
            result = rag.answer(question, top_k=top_k, use_llm=use_llm, meeting_id=selected_meeting_id, user_id=user_id)
        loading.empty()

        answer_col, source_col = st.columns([1.35, 0.65], gap="large")
        with answer_col:
            st.markdown("### 回答")
            st.markdown(result["answer"])
            with st.expander("查看检索片段"):
                for index, context in enumerate(result.get("contexts", []), start=1):
                    st.markdown(f"**片段 {index}**")
                    st.write(context)

        with source_col:
            st.markdown("### 来源")
            sources = result.get("sources") or []
            if not sources:
                st.info("没有检索到来源。")
            for source in sources:
                st.markdown(
                    f"""
                    <div class="source-row">
                        <strong>#{source.get('meeting_id')} {source.get('title')}</strong>
                        <span>{source.get('meeting_date') or '未填写日期'} | chunk {source.get('chunk_index')} | score {source.get('score', 0):.3f}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        st.toast("问答完成")
    except VectorStoreUnavailableError as exc:
        loading.empty()
        st.error(f"ChromaDB 暂不可用：{exc}")
        st.info("请先执行 `python -m pip install chromadb`，并确保当前 Python 环境可以导入 chromadb。")
    except Exception as exc:
        loading.empty()
        st.error(f"问答失败：{exc}")
elif ask:
    st.warning("请先输入问题。")
