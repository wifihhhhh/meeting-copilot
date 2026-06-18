import streamlit as st

from auth_ui import current_user_id, render_auth_forms, render_user_box
from config import APP_NAME, DEFAULT_MODEL
from database.repository import MeetingRepository
from database.sqlite import init_db
from ui import apply_modern_theme, bento_card, feature_chip, metric_card, platform_hero


st.set_page_config(page_title=APP_NAME, page_icon="MC", layout="wide")
apply_modern_theme()
init_db()

if "_shutdown_tip_printed" not in st.session_state:
    print(
        "\n关闭 Streamlit 服务的 PowerShell 命令：\n"
        "  Get-Process streamlit,python -ErrorAction SilentlyContinue\n"
        "  Stop-Process -Id 进程ID\n",
        flush=True,
    )
    st.session_state._shutdown_tip_printed = True

if "model" not in st.session_state:
    st.session_state.model = DEFAULT_MODEL
if "use_llm" not in st.session_state:
    st.session_state.use_llm = True

platform_hero(
    "Meeting Copilot",
    "把会议记录变成结构化纪要、行动项、历史知识库和可追问答案。",
)

if current_user_id() is None:
    left, right = st.columns([1.22, 0.78], gap="large")
    with left:
        st.markdown("### 核心能力")
        f1, f2 = st.columns(2, gap="large")
        with f1:
            feature_chip("01", "结构化抽取", "从会议文本中提取主题、议题、发言要点、决议和待办。")
        with f2:
            feature_chip("02", "可编辑导出", "支持修改 JSON/Markdown，并导出 Markdown、JSON、PDF。")
        st.markdown('<div class="feature-spacer"></div>', unsafe_allow_html=True)
        f3, f4 = st.columns(2, gap="large")
        with f3:
            feature_chip("03", "历史检索", "SQLite 保存会议记录，按账号隔离，支持关键词查询。")
        with f4:
            feature_chip("04", "RAG 问答", "ChromaDB 建立私有知识库，跨会议追问并显示来源。")
        st.caption("本地开发版：账号、会议和向量索引都保存在项目目录，不会自动上传云端。")
    with right:
        render_auth_forms()
    st.stop()

render_user_box()
repo = MeetingRepository()
user_id = current_user_id()
meetings = repo.list_meetings(user_id=user_id)
actions = repo.list_action_items(user_id=user_id)
decisions = repo.list_decisions(user_id=user_id)

c1, c2, c3, c4 = st.columns(4)
with c1:
    metric_card("我的会议", str(len(meetings)))
with c2:
    metric_card("我的待办", str(len(actions)))
with c3:
    metric_card("我的决议", str(len(decisions)))
with c4:
    metric_card("当前模型", st.session_state.model)

st.markdown("### 工作台")
flow_cols = st.columns([1.15, 1, 1, 1], gap="large")
items = [
    ("Start", "输入会议记录", "粘贴会议逐字稿，或上传 TXT / Markdown 转写文本。", True),
    ("Extract", "生成纪要", "按 JSON Schema 生成议题、决议、待办和摘要。", False),
    ("Export", "编辑导出", "修改内容后导出 Markdown、JSON 或 PDF。", False),
    ("Ask", "跨会追问", "只检索当前账号的历史会议，并给出来源片段。", False),
]
for col, (step, title, body, large) in zip(flow_cols, items):
    with col:
        bento_card(step, title, body, large=large)

st.markdown("### 快速入口")
q1, q2, q3 = st.columns(3, gap="large")
with q1:
    st.page_link("pages/1_generate_minutes.py", label="生成会议纪要", icon=":material/edit_note:")
with q2:
    st.page_link("pages/2_history.py", label="查询历史会议", icon=":material/manage_search:")
with q3:
    st.page_link("pages/3_meeting_qa.py", label="跨会议问答", icon=":material/forum:")
