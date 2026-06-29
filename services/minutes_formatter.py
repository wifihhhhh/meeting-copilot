from typing import Any


def format_minutes(minutes: dict[str, Any] | Any) -> str:
    if hasattr(minutes, "model_dump"):
        minutes = minutes.model_dump()

    title = minutes.get("title") or "未命名会议"
    date = minutes.get("date") or "未填写"
    time = minutes.get("time") or "未填写"
    participants = "、".join(minutes.get("participants") or []) or "未识别"

    lines = [
        "# 会议纪要",
        "",
        f"**主题：** {title}  ",
        f"**时间：** {date} {time}  ",
        f"**参会人：** {participants}",
        "",
        "## 会议摘要",
        minutes.get("summary") or "暂无摘要。",
        "",
        "## 议题讨论",
    ]

    for index, topic in enumerate(minutes.get("topics") or [], start=1):
        lines.extend(["", f"### 议题 {index}：{topic.get('title', '未命名议题')}"])
        for point in topic.get("discussion_points") or []:
            if isinstance(point, dict):
                speaker = point.get("speaker") or "发言"
                content = point.get("point") or point.get("content") or ""
                lines.append(f"- {speaker}：{content}")
            else:
                lines.append(f"- {point}")
        for decision in topic.get("decisions") or []:
            content = decision if isinstance(decision, str) else decision.get("content", "")
            lines.append(f"- 决议：{content}")

    lines.extend(["", "## 决议事项"])
    decisions = minutes.get("decisions") or []
    if decisions:
        for index, item in enumerate(decisions, start=1):
            owner = item.get("owner") or "未指定"
            deadline = item.get("deadline") or "未指定"
            lines.append(f"{index}. {owner}：{item.get('content', '')} | 截止：{deadline}")
    else:
        lines.append("暂无明确决议。")

    lines.extend(["", "## Action Items"])
    actions = minutes.get("action_items") or []
    if actions:
        for index, item in enumerate(actions, start=1):
            owner = item.get("owner") or "未指定"
            deadline = item.get("deadline") or "未指定"
            status = item.get("status") or "待办"
            lines.append(f"{index}. {owner} -> {item.get('task', '')} | 截止：{deadline} | 状态：{status}")
    else:
        lines.append("暂无待办事项。")

    return "\n".join(lines).strip() + "\n"
