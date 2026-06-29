import streamlit as st
import streamlit.components.v1 as components
import json
from html import escape

from auth_ui import render_user_box, require_login
from config import DEFAULT_EMBEDDING_PROVIDER
from database.repository import MeetingRepository
from services.export_service import ExportService
from services.meeting_insights import (
    STATUS_COLORS,
    STATUS_ORDER,
    build_action_board,
    build_knowledge_graph_html,
    insight_css,
    normalize_status,
    render_task_card,
)
from services.minutes_formatter import format_minutes
from services.rag_service import RAGService
from services.task_analytics import calculate_task_statistics, filter_action_items, list_owners
from ui import apply_modern_theme, metric_card, page_header

st.session_state.setdefault("embedding_provider", DEFAULT_EMBEDDING_PROVIDER)


st.set_page_config(page_title="历史会议", page_icon="MC", layout="wide")
apply_modern_theme()
user_id = require_login()
render_user_box()
page_header("历史会议与知识资产", "浏览纪要、查看会议关系图，并把待办事项转化为可追踪的执行看板。", "知识图谱 + Action Board")
st.markdown(insight_css(), unsafe_allow_html=True)

repo = MeetingRepository()
exporter = ExportService()


def render_glass_table(rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    headers = list(rows[0])
    head = "".join(f"<th>{escape(str(header))}</th>" for header in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{escape(str(row.get(header) or '—'))}</td>" for header in headers) + "</tr>"
        for row in rows
    )
    st.markdown(
        f'<div class="history-glass-table"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>',
        unsafe_allow_html=True,
    )

keyword = st.text_input(
    "搜索会议",
    placeholder="输入关键词，例如：微服务、王工、分享裂变、DDD",
    label_visibility="collapsed",
)

meetings = repo.list_meetings(keyword, user_id=user_id)
all_meetings = repo.list_meetings(user_id=user_id)
all_actions = repo.list_action_items(user_id=user_id)
all_decisions = repo.list_decisions(user_id=user_id)
meeting_titles = {item.id: item.title for item in all_meetings}
shared_meeting_ids = {item.id for item in all_meetings if item.is_shared}
private_meetings = [item for item in all_meetings if not item.is_shared]
private_meeting_ids = {item.id for item in private_meetings}
private_actions = [item for item in all_actions if item.meeting_id in private_meeting_ids]
private_decisions = [item for item in all_decisions if item.meeting_id in private_meeting_ids]

done_count = sum(1 for item in all_actions if normalize_status(item.status) == "已完成")
active_count = sum(1 for item in all_actions if normalize_status(item.status) in {"待办", "进行中", "延期"})

c1, c2, c3, c4 = st.columns(4)
with c1:
    metric_card("匹配会议", str(len(meetings)))
with c2:
    metric_card("历史会议", str(len(all_meetings)))
with c3:
    metric_card("待跟进", str(active_count))
with c4:
    metric_card("已完成", str(done_count))

list_tab, graph_tab, board_tab = st.tabs(["会议列表", "知识图谱", "待办看板"])

with list_tab:
    if not meetings:
        st.info("当前账号还没有会议记录，或没有匹配搜索关键词。")

    for meeting in meetings:
        actions = repo.list_action_items(meeting.id, user_id=user_id)
        decisions = repo.list_decisions(meeting.id, user_id=user_id)
        summary = meeting.minutes_json.get("summary") or "暂无摘要"

        expander_label = (
            f"**{meeting.title}**  ·  会议 ID：{meeting.id}  ·  "
            f"日期：{meeting.meeting_date or '未填写'}  ·  创建：{meeting.created_at}"
        )
        with st.expander(expander_label, expanded=False):
            top_left, top_right = st.columns([3, 1], gap="large")
            with top_left:
                st.caption("会议摘要")
                st.write(summary)
            with top_right:
                metric_card("待办", str(len(actions)))
                metric_card("决议", str(len(decisions)))

            tab1, tab2, tab3, tab4, tab5 = st.tabs(["纪要", "待办", "决议", "JSON", "管理"])
            with tab1:
                regenerated = format_minutes(meeting.minutes_json)
                st.markdown(regenerated)
                md_path = exporter.export_markdown(regenerated, meeting.title)
                st.download_button(
                    "下载 Markdown",
                    md_path.read_bytes(),
                    file_name=md_path.name,
                    key=f"download-md-{meeting.id}",
                )
            with tab2:
                if actions:
                    render_glass_table(
                        [
                            {
                                "负责人": item.owner,
                                "任务": item.task,
                                "截止时间": item.deadline,
                                "状态": normalize_status(item.status),
                            }
                            for item in actions
                        ],
                    )
                else:
                    st.info("暂无待办事项。")
            with tab3:
                if decisions:
                    render_glass_table(
                        [
                            {
                                "负责人": item.owner,
                                "决议": item.content,
                                "议题": item.topic,
                                "截止时间": item.deadline,
                            }
                            for item in decisions
                        ],
                    )
                else:
                    st.info("暂无明确决议。")
            with tab4:
                json_text = json.dumps(meeting.minutes_json, ensure_ascii=False, indent=2)
                st.markdown(
                    f'<pre class="history-json-panel"><code>{escape(json_text)}</code></pre>',
                    unsafe_allow_html=True,
                )
            with tab5:
                if meeting.is_shared:
                    st.info(f"系统共享只读数据 · 来源：{meeting.source} · 外部 ID：{meeting.external_id}")
                else:
                    st.warning("删除后会移除这场会议、对应待办、决议、评估记录，并尽量清理 RAG 向量索引。")
                    confirm_delete = st.checkbox(
                        f"确认删除 #{meeting.id} {meeting.title}",
                        key=f"confirm-delete-meeting-{meeting.id}",
                    )
                    if st.button(
                        "删除这场会议",
                        key=f"delete-meeting-{meeting.id}",
                        type="secondary",
                        disabled=not confirm_delete,
                        use_container_width=True,
                    ):
                        try:
                            try:
                                RAGService(
                                    repository=repo,
                                    embedding_provider=st.session_state.get("embedding_provider", "hash"),
                                ).delete_meeting_index(meeting.id)
                            except Exception as rag_exc:
                                st.warning(f"会议会从 SQLite 删除，但 RAG 索引清理失败：{rag_exc}")
                            deleted = repo.delete_meeting(meeting.id, user_id=user_id)
                            if deleted:
                                st.toast("会议已删除")
                                st.rerun()
                            st.info("这条会议记录已经不存在。")
                        except PermissionError as exc:
                            st.error(str(exc))

with graph_tab:
    st.caption("仅展示当前账号创建的会议、议题、负责人、待办和决议；系统共享课程数据不进入关系图。")
    graph_html = build_knowledge_graph_html(private_meetings, private_actions, private_decisions)
    components.html(graph_html, height=700, scrolling=False)

with board_tab:
    st.caption("仅展示当前账号会议产生的待办；系统共享课程数据不进入看板。")
    if not private_actions:
        st.info("当前账号还没有待办事项。请先生成至少一份包含 Action Items 的会议纪要。")
    else:
        f1, f2, f3 = st.columns(3, gap="large")
        with f1:
            owner_filter = st.selectbox("负责人", ["全部"] + list_owners(private_actions))
        with f2:
            status_filter = st.selectbox("任务状态", ["全部"] + STATUS_ORDER)
        with f3:
            due_filter = st.selectbox("截止时间", ["全部", "逾期", "今天到期", "未来3天", "未设置截止时间"])

        filtered_actions = filter_action_items(
            private_actions,
            owner="" if owner_filter == "全部" else owner_filter,
            status="" if status_filter == "全部" else status_filter,
            due=due_filter,
        )
        stats = calculate_task_statistics(private_actions)
        s1, s2, s3, s4 = st.columns(4)
        with s1:
            metric_card("完成率", f"{stats.completion_rate:.1f}%")
        with s2:
            metric_card("已逾期", str(stats.overdue))
        with s3:
            metric_card("今天到期", str(stats.due_today))
        with s4:
            metric_card("未来 3 天", str(stats.upcoming))

        columns = st.columns(len(STATUS_ORDER), gap="medium")
        board = build_action_board(filtered_actions)
        for column, board_column in zip(columns, board):
            with column:
                color = STATUS_COLORS.get(board_column.status, "#e5e7eb")
                st.markdown(
                    f"""
                    <div class="kanban-card">
                      <div class="kanban-title">
                        <h4>{board_column.status}</h4>
                        <span class="kanban-count">{len(board_column.items)}</span>
                      </div>
                    """,
                    unsafe_allow_html=True,
                )
                for item in board_column.items[:12]:
                    st.markdown(render_task_card(item, meeting_titles.get(item.meeting_id, "")), unsafe_allow_html=True)
                    current_status = normalize_status(item.status)
                    next_status = st.selectbox(
                        "状态",
                        STATUS_ORDER,
                        index=STATUS_ORDER.index(current_status) if current_status in STATUS_ORDER else 0,
                        key=f"action-status-{item.id}",
                        label_visibility="collapsed",
                        disabled=item.meeting_id in shared_meeting_ids,
                    )
                    if item.meeting_id in shared_meeting_ids:
                        st.caption("系统共享数据 · 只读")
                    elif next_status != current_status:
                        if st.button("更新", key=f"update-action-{item.id}", use_container_width=True):
                            repo.update_action_item_status(item.id, next_status, user_id=user_id)
                            st.toast(f"已更新为：{next_status}")
                            st.rerun()
                    st.markdown(
                        f"<div style='height:4px;border-radius:999px;background:{color};opacity:.72;margin:6px 0 14px;'></div>",
                        unsafe_allow_html=True,
                    )
                if len(board_column.items) > 12:
                    st.caption(f"还有 {len(board_column.items) - 12} 条未显示，可通过搜索或后续分页查看。")
                st.markdown("</div>", unsafe_allow_html=True)

