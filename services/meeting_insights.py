from __future__ import annotations

import html
import math
import re
from dataclasses import dataclass
from typing import Iterable

from database.models import ActionItemRecord, DecisionRecord, MeetingRecord


STATUS_ORDER = ["待办", "进行中", "已完成", "延期", "取消"]
STATUS_COLORS = {
    "待办": "#dbeafe",
    "进行中": "#ccfbf1",
    "已完成": "#dcfce7",
    "延期": "#fee2e2",
    "取消": "#e5e7eb",
}


@dataclass(frozen=True)
class ActionBoardColumn:
    status: str
    items: list[ActionItemRecord]


def build_action_board(actions: Iterable[ActionItemRecord]) -> list[ActionBoardColumn]:
    grouped = {status: [] for status in STATUS_ORDER}
    for item in actions:
        status = normalize_status(item.status)
        grouped.setdefault(status, []).append(item)
    return [ActionBoardColumn(status=status, items=grouped.get(status, [])) for status in STATUS_ORDER]


def normalize_status(status: str | None) -> str:
    clean = (status or "").strip()
    aliases = {
        "todo": "待办",
        "doing": "进行中",
        "done": "已完成",
        "delayed": "延期",
        "cancelled": "取消",
        "canceled": "取消",
        "待处理": "待办",
        "处理中": "进行中",
        "完成": "已完成",
        "寰呭姙": "待办",
        "杩涜涓?": "进行中",
        "宸插畬鎴?": "已完成",
        "寤舵湡": "延期",
        "鍙栨秷": "取消",
    }
    return aliases.get(clean, clean if clean in STATUS_ORDER else "待办")


def extract_topic_keywords(meeting: MeetingRecord, decisions: list[DecisionRecord], limit: int = 5) -> list[str]:
    candidates: list[str] = []
    minutes = meeting.minutes_json or {}
    for topic in minutes.get("topics") or []:
        title = str(topic.get("title") or "").strip()
        if title:
            candidates.append(_clean_topic(title))
    for decision in decisions:
        if decision.topic:
            candidates.append(_clean_topic(decision.topic))
        candidates.extend(_keywords_from_text(decision.content))
    candidates.extend(_keywords_from_text(meeting.title))

    result: list[str] = []
    for item in candidates:
        item = item.strip(" ：:，,。.；;")
        if len(item) < 2:
            continue
        if item not in result:
            result.append(item)
        if len(result) >= limit:
            break
    return result


def _clean_topic(text: str) -> str:
    text = re.sub(r"^议题[一二三四五六七八九十\d]+[:：]?", "", text).strip()
    return text[:18]


def _keywords_from_text(text: str) -> list[str]:
    protected = re.findall(r"[A-Za-z][A-Za-z0-9_+-]{1,20}", text)
    chinese = re.findall(r"[\u4e00-\u9fa5]{2,8}", text)
    stop = {"会议", "讨论", "决定", "决议", "负责", "完成", "方案", "进行", "当前", "本次", "需要", "已经", "一个"}
    words = [word for word in protected + chinese if word not in stop]
    return words[:8]


def build_knowledge_graph_html(
    meetings: list[MeetingRecord],
    actions: list[ActionItemRecord],
    decisions: list[DecisionRecord],
    height: int = 620,
) -> str:
    nodes: dict[str, dict[str, str]] = {}
    edges: list[tuple[str, str, str, str]] = []

    meetings_by_id = {meeting.id: meeting for meeting in meetings}
    decisions_by_meeting: dict[int, list[DecisionRecord]] = {}
    actions_by_meeting: dict[int, list[ActionItemRecord]] = {}
    for decision in decisions:
        decisions_by_meeting.setdefault(decision.meeting_id, []).append(decision)
    for action in actions:
        actions_by_meeting.setdefault(action.meeting_id, []).append(action)

    def add_node(node_id: str, label: str, kind: str) -> None:
        nodes.setdefault(node_id, {"label": label, "kind": kind})

    for meeting in meetings[:10]:
        meeting_id = f"m:{meeting.id}"
        add_node(meeting_id, meeting.title or f"会议 {meeting.id}", "meeting")
        for topic in extract_topic_keywords(meeting, decisions_by_meeting.get(meeting.id, []), limit=3):
            topic_id = f"t:{topic}"
            add_node(topic_id, topic, "topic")
            edges.append((meeting_id, topic_id, "讨论", "topic"))

    for action in actions[:36]:
        meeting = meetings_by_id.get(action.meeting_id)
        owner = (action.owner or "未指定").strip()
        task = (action.task or "待办事项").strip()
        owner_id = f"p:{owner}"
        action_id = f"a:{action.id}"
        add_node(owner_id, owner, "person")
        add_node(action_id, _short(task, 20), "action")
        edges.append((owner_id, action_id, "负责", "action"))
        if meeting:
            edges.append((f"m:{meeting.id}", action_id, "产生待办", "action"))

    for decision in decisions[:36]:
        meeting = meetings_by_id.get(decision.meeting_id)
        owner = (decision.owner or "").strip()
        content = (decision.content or "决议").strip()
        decision_id = f"d:{decision.id}"
        add_node(decision_id, _short(content, 22), "decision")
        if owner:
            owner_id = f"p:{owner}"
            add_node(owner_id, owner, "person")
            edges.append((owner_id, decision_id, "参与决议", "decision"))
        if meeting:
            edges.append((f"m:{meeting.id}", decision_id, "形成决议", "decision"))
        if decision.topic:
            topic = _clean_topic(decision.topic)
            topic_id = f"t:{topic}"
            add_node(topic_id, topic, "topic")
            edges.append((topic_id, decision_id, "结论", "decision"))

    if not nodes:
        return _empty_graph_html(height)

    positions = _layout_nodes(nodes, width=1040, height=height - 44)
    svg_nodes = []
    svg_edges = []
    for source, target, label, kind in edges[:110]:
        if source not in positions or target not in positions:
            continue
        x1, y1 = positions[source]
        x2, y2 = positions[target]
        color = _edge_color(kind)
        svg_edges.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{color}" stroke-width="1.05" stroke-opacity="0.52" />'
        )
    for node_id, meta in nodes.items():
        x, y = positions[node_id]
        kind = meta["kind"]
        label = html.escape(_short(meta["label"], 16))
        fill, glow, radius = _node_style(kind)
        svg_nodes.append(
            f'<g class="node node-{kind}">'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" fill="{fill}" fill-opacity=".72" filter="url(#{glow})" />'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" fill="none" stroke="rgba(226,232,255,.54)" stroke-width="1" />'
            f'<text x="{x:.1f}" y="{y + radius + 16:.1f}" class="node-label">{label}</text>'
            f'</g>'
        )

    legend = "".join(
        f'<span><i style="background:{color}"></i>{name}</span>'
        for name, color in [
            ("会议", "linear-gradient(135deg,#dbeafe,#a78bfa)"),
            ("人员", "linear-gradient(135deg,#bae6fd,#818cf8)"),
            ("议题", "linear-gradient(135deg,#c4b5fd,#60a5fa)"),
            ("决议", "linear-gradient(135deg,#a5b4fc,#c084fc)"),
            ("待办", "linear-gradient(135deg,#93c5fd,#8b5cf6)"),
        ]
    )
    return f"""
    {insight_css()}
    <div class="insight-graph-wrap">
      <div class="insight-graph-head">
        <div>
          <div class="insight-kicker">Meeting Knowledge Graph</div>
          <h3>会议知识关系图</h3>
        </div>
        <div class="graph-legend">{legend}</div>
      </div>
      <svg viewBox="0 0 1040 {height}" class="insight-graph" role="img" aria-label="会议知识关系图">
        <defs>
          <linearGradient id="meeting-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#dbeafe"/>
            <stop offset="52%" stop-color="#a78bfa"/>
            <stop offset="100%" stop-color="#7c3aed"/>
          </linearGradient>
          <linearGradient id="person-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#bae6fd"/>
            <stop offset="100%" stop-color="#818cf8"/>
          </linearGradient>
          <linearGradient id="topic-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#c4b5fd"/>
            <stop offset="100%" stop-color="#60a5fa"/>
          </linearGradient>
          <linearGradient id="decision-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#a5b4fc"/>
            <stop offset="100%" stop-color="#c084fc"/>
          </linearGradient>
          <linearGradient id="action-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#93c5fd"/>
            <stop offset="100%" stop-color="#8b5cf6"/>
          </linearGradient>
          <filter id="glow-blue"><feGaussianBlur stdDeviation="5" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
          <filter id="glow-cyan"><feGaussianBlur stdDeviation="4" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
          <filter id="glow-pink"><feGaussianBlur stdDeviation="4" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
          <filter id="glow-green"><feGaussianBlur stdDeviation="4" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
        </defs>
        <rect x="0" y="0" width="1040" height="{height}" rx="28" fill="rgba(255,255,255,.055)" />
        <g class="edges">{''.join(svg_edges)}</g>
        <g class="nodes">{''.join(svg_nodes)}</g>
      </svg>
    </div>
    """


def insight_css() -> str:
    return """
    <style>
    .insight-graph-wrap,
    .kanban-card {
        border-radius: 24px;
        padding: 18px;
        background: rgba(255,255,255,.16);
        backdrop-filter: blur(22px) saturate(1.18);
        box-shadow: 0 24px 70px rgba(0,0,0,.24);
    }
    .insight-graph-head {
        display:flex;
        align-items:flex-start;
        justify-content:space-between;
        gap:18px;
        margin-bottom:10px;
    }
    .insight-kicker {
        color:rgba(255,255,255,.72);
        font-size:12px;
        font-weight:800;
        text-transform:uppercase;
    }
    .insight-graph-head h3 {
        margin:4px 0 0;
        color:white;
        font-size:24px;
    }
    .graph-legend {
        display:flex;
        gap:10px;
        flex-wrap:wrap;
        justify-content:flex-end;
        color:rgba(255,255,255,.80);
        font-size:12px;
    }
    .graph-legend span {
        display:inline-flex;
        align-items:center;
        gap:6px;
        padding:6px 9px;
        border-radius:999px;
        background:rgba(255,255,255,.08);
        backdrop-filter:blur(12px) saturate(1.12);
    }
    .graph-legend i {
        display:inline-block;
        width:10px;
        height:10px;
        border-radius:50%;
    }
    .insight-graph {
        width:100%;
        min-height:520px;
        overflow:visible;
    }
    .edge-label {
        fill:rgba(255,255,255,.66);
        font-size:11px;
        text-anchor:middle;
        paint-order:stroke;
        stroke:rgba(5,8,22,.72);
        stroke-width:3px;
    }
    .node-label {
        fill:rgba(248,250,252,.90);
        font-size:13px;
        font-weight:750;
        text-anchor:middle;
        paint-order:stroke;
        stroke:rgba(5,8,22,.62);
        stroke-width:3px;
    }
    .node {
        transition: transform .18s ease, filter .18s ease;
        transform-box: fill-box;
        transform-origin: center;
    }
    .node:hover {
        transform: scale(1.08);
        filter: saturate(1.22) brightness(1.1);
    }
    .kanban-card {
        min-height: 210px;
        position:relative;
        overflow:hidden;
    }
    .kanban-card:after {
        content:"";
        position:absolute;
        inset:0;
        border-radius:inherit;
        padding:1px;
        background:linear-gradient(135deg, rgba(255,255,255,.88), rgba(255,255,255,.16), rgba(255,255,255,0));
        pointer-events:none;
        -webkit-mask:linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
        -webkit-mask-composite:xor;
        mask-composite:exclude;
    }
    .kanban-title {
        display:flex;
        justify-content:space-between;
        align-items:center;
        gap:10px;
        margin-bottom:12px;
    }
    .kanban-title h4 {
        margin:0;
        color:white;
        font-size:17px;
    }
    .kanban-count {
        min-width:28px;
        text-align:center;
        padding:3px 8px;
        border-radius:999px;
        color:#07111f;
        background:rgba(255,255,255,.82);
        font-weight:800;
    }
    .task-mini {
        padding:12px;
        border-radius:18px;
        background:rgba(255,255,255,.18);
        margin-bottom:10px;
        color:white;
        box-shadow:0 14px 30px rgba(0,0,0,.15);
    }
    .task-mini strong {
        display:block;
        font-size:13px;
        margin-bottom:5px;
        color:white;
    }
    .task-mini span {
        display:block;
        color:rgba(255,255,255,.75);
        font-size:12px;
        line-height:1.45;
    }
    </style>
    """


def render_task_card(item: ActionItemRecord, meeting_title: str = "") -> str:
    owner = html.escape(item.owner or "未指定")
    task = html.escape(_short(item.task or "待办事项", 42))
    deadline = html.escape(item.deadline or "未填写截止时间")
    source = html.escape(_short(meeting_title, 22)) if meeting_title else ""
    source_html = f"<span>来源：{source}</span>" if source else ""
    return f"""
    <div class="task-mini">
      <strong>{owner} · {deadline}</strong>
      <span>{task}</span>
      {source_html}
    </div>
    """


def _layout_nodes(nodes: dict[str, dict[str, str]], width: int, height: int) -> dict[str, tuple[float, float]]:
    by_kind: dict[str, list[str]] = {}
    for node_id, meta in nodes.items():
        by_kind.setdefault(meta["kind"], []).append(node_id)
    positions: dict[str, tuple[float, float]] = {}

    lanes = {
        "topic": (0.50, 0.18, 700, 2),
        "person": (0.18, 0.52, 250, 4),
        "meeting": (0.50, 0.50, 360, 2),
        "decision": (0.82, 0.42, 260, 4),
        "action": (0.58, 0.80, 640, 2),
    }
    for kind in ["topic", "person", "meeting", "decision", "action"]:
        ids = by_kind.get(kind, [])
        if not ids:
            continue
        cx_ratio, cy_ratio, span, columns = lanes[kind]
        positions.update(_place_grid(ids, width * cx_ratio, height * cy_ratio, span, columns, width, height))
    return positions


def _place_grid(
    ids: list[str],
    center_x: float,
    center_y: float,
    span: float,
    columns: int,
    width: int,
    height: int,
) -> dict[str, tuple[float, float]]:
    columns = max(1, min(columns, len(ids)))
    row_gap = 88
    col_gap = span / max(columns - 1, 1)
    rows = math.ceil(len(ids) / columns)
    result: dict[str, tuple[float, float]] = {}
    for index, node_id in enumerate(ids):
        row = index // columns
        col = index % columns
        items_in_row = min(columns, len(ids) - row * columns)
        row_width = col_gap * max(items_in_row - 1, 0)
        x = center_x - row_width / 2 + col * col_gap
        y = center_y + (row - (rows - 1) / 2) * row_gap
        result[node_id] = (max(58, min(width - 58, x)), max(60, min(height - 34, y)))
    return result


def _node_style(kind: str) -> tuple[str, str, int]:
    if kind == "meeting":
        return ("url(#meeting-gradient)", "glow-blue", 30)
    fills = {
        "person": ("url(#person-gradient)", "glow-cyan", 21),
        "topic": ("url(#topic-gradient)", "glow-blue", 18),
        "decision": ("url(#decision-gradient)", "glow-pink", 19),
        "action": ("url(#action-gradient)", "glow-blue", 18),
    }
    fill, glow, radius = fills.get(kind, ("url(#topic-gradient)", "glow-blue", 18))
    return fill, glow, radius


def _edge_color(kind: str) -> str:
    return {
        "topic": "rgba(147,197,253,.46)",
        "decision": "rgba(192,132,252,.48)",
        "action": "rgba(129,140,248,.44)",
    }.get(kind, "rgba(191,219,254,.38)")


def _short(text: str, limit: int) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    return clean if len(clean) <= limit else clean[: limit - 1] + "…"


def _empty_graph_html(height: int) -> str:
    return f"""
    <div class="insight-graph-wrap" style="min-height:{height}px;display:grid;place-items:center;color:white;">
      <div>
        <div class="insight-kicker">Meeting Knowledge Graph</div>
        <h3>暂无可绘制的会议关系</h3>
      </div>
    </div>
    """
