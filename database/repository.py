import json
from typing import Any

from sqlalchemy import delete, or_, select

from database.models import (
    ActionItem,
    ActionItemRecord,
    Decision,
    DecisionRecord,
    EvaluationResult,
    EvaluationResultRecord,
    Meeting,
    MeetingRecord,
    QARecord,
    utc_now_text,
)
from database.sqlite import get_session, init_db


DEFAULT_USER_ID = 1


class MeetingRepository:
    def __init__(self) -> None:
        init_db()

    def create_meeting(
        self,
        title: str,
        meeting_date: str | None,
        raw_text: str,
        minutes_json: dict[str, Any],
        minutes_markdown: str,
        user_id: int | None = None,
        source: str = "user",
        external_id: str = "",
        is_shared: bool = False,
    ) -> int:
        with get_session() as session:
            meeting = Meeting(
                user_id=user_id or DEFAULT_USER_ID,
                title=title,
                meeting_date=meeting_date,
                raw_text=raw_text,
                minutes_json=json.dumps(minutes_json, ensure_ascii=False),
                minutes_markdown=minutes_markdown,
                source=source,
                external_id=external_id,
                is_shared=is_shared,
            )
            session.add(meeting)
            session.flush()
            self._replace_children(session, meeting.id, minutes_json)
            return int(meeting.id)

    def update_meeting(
        self,
        meeting_id: int,
        minutes_json: dict[str, Any],
        minutes_markdown: str,
        user_id: int | None = None,
    ) -> None:
        with get_session() as session:
            meeting = session.get(Meeting, meeting_id)
            if meeting is None:
                raise ValueError(f"Meeting not found: {meeting_id}")
            if meeting.is_shared:
                raise PermissionError("共享数据集会议为只读，不能在用户工作台中修改。")
            if user_id is not None and meeting.user_id != user_id:
                raise PermissionError("无权修改其他用户的会议。")
            meeting.title = minutes_json.get("title") or "未命名会议"
            meeting.meeting_date = minutes_json.get("date")
            meeting.minutes_json = json.dumps(minutes_json, ensure_ascii=False)
            meeting.minutes_markdown = minutes_markdown
            meeting.updated_at = utc_now_text()
            self._replace_children(session, meeting_id, minutes_json)

    def list_meetings(self, keyword: str = "", user_id: int | None = None) -> list[MeetingRecord]:
        keyword = keyword.strip()
        with get_session() as session:
            conditions = []
            if user_id is not None:
                conditions.append(or_(Meeting.user_id == user_id, Meeting.is_shared.is_(True)))
            if keyword:
                like = f"%{keyword}%"
                conditions.append(
                    or_(
                        Meeting.title.like(like),
                        Meeting.raw_text.like(like),
                        Meeting.minutes_markdown.like(like),
                    )
                )
            stmt = select(Meeting)
            if conditions:
                stmt = stmt.where(*conditions)
            stmt = stmt.order_by(Meeting.created_at.desc())
            meetings = session.execute(stmt).scalars().all()
            return [self._to_record(meeting) for meeting in meetings]

    def get_meeting(self, meeting_id: int, user_id: int | None = None) -> MeetingRecord | None:
        with get_session() as session:
            meeting = session.get(Meeting, meeting_id)
            if meeting is None:
                return None
            if user_id is not None and meeting.user_id != user_id and not meeting.is_shared:
                return None
            return self._to_record(meeting)

    def delete_meeting(self, meeting_id: int, user_id: int | None = None) -> bool:
        with get_session() as session:
            meeting = session.get(Meeting, meeting_id)
            if meeting is None:
                return False
            if meeting.is_shared:
                raise PermissionError("共享数据集会议为只读，不能删除。")
            if user_id is not None and meeting.user_id != user_id:
                raise PermissionError("无权删除其他用户的会议。")

            session.execute(delete(ActionItem).where(ActionItem.meeting_id == meeting_id))
            session.execute(delete(Decision).where(Decision.meeting_id == meeting_id))
            session.execute(delete(EvaluationResult).where(EvaluationResult.meeting_id == meeting_id))
            session.delete(meeting)
            return True

    def list_action_items(self, meeting_id: int | None = None, user_id: int | None = None) -> list[ActionItemRecord]:
        with get_session() as session:
            stmt = select(ActionItem)
            if user_id is not None:
                stmt = stmt.join(Meeting).where(or_(Meeting.user_id == user_id, Meeting.is_shared.is_(True)))
            if meeting_id is not None:
                stmt = stmt.where(ActionItem.meeting_id == meeting_id)
            stmt = stmt.order_by(ActionItem.id)
            rows = session.execute(stmt).scalars().all()
            return [
                ActionItemRecord(
                    id=row.id,
                    meeting_id=row.meeting_id,
                    owner=row.owner,
                    task=row.task,
                    deadline=row.deadline,
                    status=row.status,
                )
                for row in rows
            ]

    def update_action_item_status(self, action_item_id: int, status: str, user_id: int | None = None) -> None:
        with get_session() as session:
            item = session.get(ActionItem, action_item_id)
            if item is None:
                raise ValueError(f"Action item not found: {action_item_id}")
            if user_id is not None:
                meeting = session.get(Meeting, item.meeting_id)
                if meeting is None or meeting.is_shared or meeting.user_id != user_id:
                    raise PermissionError("无权修改其他用户的待办事项。")
            item.status = status

    def list_decisions(self, meeting_id: int | None = None, user_id: int | None = None) -> list[DecisionRecord]:
        with get_session() as session:
            stmt = select(Decision)
            if user_id is not None:
                stmt = stmt.join(Meeting).where(or_(Meeting.user_id == user_id, Meeting.is_shared.is_(True)))
            if meeting_id is not None:
                stmt = stmt.where(Decision.meeting_id == meeting_id)
            stmt = stmt.order_by(Decision.id)
            rows = session.execute(stmt).scalars().all()
            return [
                DecisionRecord(
                    id=row.id,
                    meeting_id=row.meeting_id,
                    owner=row.owner,
                    content=row.content,
                    deadline=row.deadline,
                    topic=row.topic,
                )
                for row in rows
            ]

    def save_evaluation_result(
        self,
        metric_name: str,
        meeting_id: int | None = None,
        user_id: int | None = None,
        precision: float | None = None,
        recall: float | None = None,
        f1: float | None = None,
        score: float | None = None,
        notes: str = "",
        payload: dict[str, Any] | None = None,
    ) -> int:
        with get_session() as session:
            result = EvaluationResult(
                user_id=user_id,
                meeting_id=meeting_id,
                metric_name=metric_name,
                precision=precision,
                recall=recall,
                f1=f1,
                score=score,
                notes=notes,
                payload_json=json.dumps(payload or {}, ensure_ascii=False),
            )
            session.add(result)
            session.flush()
            return int(result.id)

    def upsert_external_meeting(
        self,
        *,
        external_id: str,
        source: str,
        raw_text: str,
        minutes_json: dict[str, Any],
        minutes_markdown: str,
        is_shared: bool = True,
        owner_user_id: int = DEFAULT_USER_ID,
    ) -> tuple[int, bool]:
        external_id = external_id.strip()
        source = source.strip()
        if not external_id or not source:
            raise ValueError("source 和 external_id 不能为空。")

        with get_session() as session:
            stmt = select(Meeting).where(Meeting.source == source, Meeting.external_id == external_id)
            meeting = session.execute(stmt).scalar_one_or_none()
            created = meeting is None
            if meeting is None:
                meeting = Meeting(
                    user_id=owner_user_id,
                    title=minutes_json.get("title") or "未命名会议",
                    meeting_date=minutes_json.get("date"),
                    raw_text=raw_text,
                    minutes_json=json.dumps(minutes_json, ensure_ascii=False),
                    minutes_markdown=minutes_markdown,
                    source=source,
                    external_id=external_id,
                    is_shared=is_shared,
                )
                session.add(meeting)
                session.flush()
            else:
                meeting.title = minutes_json.get("title") or "未命名会议"
                meeting.meeting_date = minutes_json.get("date")
                meeting.raw_text = raw_text
                meeting.minutes_json = json.dumps(minutes_json, ensure_ascii=False)
                meeting.minutes_markdown = minutes_markdown
                meeting.is_shared = is_shared
                meeting.updated_at = utc_now_text()
            self._replace_children(session, int(meeting.id), minutes_json)
            return int(meeting.id), created

    def list_evaluation_results(
        self,
        meeting_id: int | None = None,
        user_id: int | None = None,
    ) -> list[EvaluationResultRecord]:
        with get_session() as session:
            stmt = select(EvaluationResult)
            if user_id is not None:
                stmt = stmt.where(EvaluationResult.user_id == user_id)
            if meeting_id is not None:
                stmt = stmt.where(EvaluationResult.meeting_id == meeting_id)
            stmt = stmt.order_by(EvaluationResult.created_at.desc())
            rows = session.execute(stmt).scalars().all()
            return [
                EvaluationResultRecord(
                    id=row.id,
                    user_id=row.user_id,
                    meeting_id=row.meeting_id,
                    metric_name=row.metric_name,
                    precision=row.precision,
                    recall=row.recall,
                    f1=row.f1,
                    score=row.score,
                    notes=row.notes,
                    payload_json=json.loads(row.payload_json or "{}"),
                    created_at=row.created_at,
                )
                for row in rows
            ]

    def save_qa(self, question: str, answer: str, sources: list[dict[str, Any]], user_id: int | None = None) -> int:
        with get_session() as session:
            record = QARecord(
                user_id=user_id or DEFAULT_USER_ID,
                question=question,
                answer=answer,
                sources_json=json.dumps(sources, ensure_ascii=False),
            )
            session.add(record)
            session.flush()
            return int(record.id)

    def keyword_search(self, query: str, limit: int = 5, user_id: int | None = None) -> list[dict[str, Any]]:
        tokens = [token for token in query.strip().split() if token]
        if not tokens:
            tokens = [query.strip()]
        meetings = self.list_meetings(user_id=user_id)
        scored = []
        for meeting in meetings:
            haystack = f"{meeting.title}\n{meeting.minutes_markdown}\n{meeting.raw_text}"
            score = sum(haystack.lower().count(token.lower()) for token in tokens)
            if score > 0:
                scored.append(
                    {
                        "meeting_id": meeting.id,
                        "title": meeting.title,
                        "meeting_date": meeting.meeting_date,
                        "content": meeting.minutes_markdown,
                        "score": float(score),
                    }
                )
        return sorted(scored, key=lambda item: item["score"], reverse=True)[:limit]

    @staticmethod
    def _replace_children(session, meeting_id: int, minutes_json: dict[str, Any]) -> None:
        session.execute(delete(ActionItem).where(ActionItem.meeting_id == meeting_id))
        session.execute(delete(Decision).where(Decision.meeting_id == meeting_id))

        for item in minutes_json.get("action_items") or []:
            session.add(
                ActionItem(
                    meeting_id=meeting_id,
                    owner=str(item.get("owner") or ""),
                    task=str(item.get("task") or item.get("content") or ""),
                    deadline=str(item.get("deadline") or ""),
                    status=str(item.get("status") or "待办"),
                )
            )

        for item in minutes_json.get("decisions") or []:
            session.add(
                Decision(
                    meeting_id=meeting_id,
                    owner=str(item.get("owner") or ""),
                    content=str(item.get("content") or item.get("task") or ""),
                    deadline=str(item.get("deadline") or ""),
                    topic=str(item.get("topic") or ""),
                )
            )

    @staticmethod
    def _to_record(meeting: Meeting) -> MeetingRecord:
        return MeetingRecord(
            id=int(meeting.id),
            user_id=int(meeting.user_id),
            title=meeting.title,
            meeting_date=meeting.meeting_date,
            raw_text=meeting.raw_text,
            minutes_json=json.loads(meeting.minutes_json),
            minutes_markdown=meeting.minutes_markdown,
            created_at=meeting.created_at,
            updated_at=meeting.updated_at,
            source=meeting.source,
            external_id=meeting.external_id,
            is_shared=bool(meeting.is_shared),
        )
