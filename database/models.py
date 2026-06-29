from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now_text() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    created_at: Mapped[str] = mapped_column(String(30), nullable=False, default=utc_now_text)

    meetings: Mapped[list["Meeting"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    qa_records: Mapped[list["QARecord"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, default=1, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    meeting_date: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    minutes_json: Mapped[str] = mapped_column(Text, nullable=False)
    minutes_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False, default="user", index=True)
    external_id: Mapped[str] = mapped_column(String(120), nullable=False, default="", index=True)
    is_shared: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    created_at: Mapped[str] = mapped_column(String(30), nullable=False, default=utc_now_text)
    updated_at: Mapped[str] = mapped_column(String(30), nullable=False, default=utc_now_text)

    user: Mapped[User] = relationship(back_populates="meetings")
    action_items: Mapped[list["ActionItem"]] = relationship(
        back_populates="meeting",
        cascade="all, delete-orphan",
        order_by="ActionItem.id",
    )
    decisions: Mapped[list["Decision"]] = relationship(
        back_populates="meeting",
        cascade="all, delete-orphan",
        order_by="Decision.id",
    )
    evaluation_results: Mapped[list["EvaluationResult"]] = relationship(
        back_populates="meeting",
        cascade="all, delete-orphan",
        order_by="EvaluationResult.id",
    )


class ActionItem(Base):
    __tablename__ = "action_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True)
    owner: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    task: Mapped[str] = mapped_column(Text, nullable=False)
    deadline: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="待办")
    created_at: Mapped[str] = mapped_column(String(30), nullable=False, default=utc_now_text)

    meeting: Mapped[Meeting] = relationship(back_populates="action_items")


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True)
    owner: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    deadline: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    topic: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    created_at: Mapped[str] = mapped_column(String(30), nullable=False, default=utc_now_text)

    meeting: Mapped[Meeting] = relationship(back_populates="decisions")


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    meeting_id: Mapped[int | None] = mapped_column(ForeignKey("meetings.id", ondelete="SET NULL"), nullable=True, index=True)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    precision: Mapped[float | None] = mapped_column(Float, nullable=True)
    recall: Mapped[float | None] = mapped_column(Float, nullable=True)
    f1: Mapped[float | None] = mapped_column(Float, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[str] = mapped_column(String(30), nullable=False, default=utc_now_text)

    meeting: Mapped[Meeting | None] = relationship(back_populates="evaluation_results")


class QARecord(Base):
    __tablename__ = "qa_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, default=1, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    sources_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[str] = mapped_column(String(30), nullable=False, default=utc_now_text)

    user: Mapped[User] = relationship(back_populates="qa_records")


@dataclass
class UserRecord:
    id: int
    username: str
    display_name: str
    created_at: str


@dataclass
class MeetingRecord:
    id: int
    user_id: int
    title: str
    meeting_date: str | None
    raw_text: str
    minutes_json: dict[str, Any]
    minutes_markdown: str
    created_at: str
    updated_at: str
    source: str = "user"
    external_id: str = ""
    is_shared: bool = False


@dataclass
class ActionItemRecord:
    id: int
    meeting_id: int
    owner: str
    task: str
    deadline: str
    status: str


@dataclass
class DecisionRecord:
    id: int
    meeting_id: int
    owner: str
    content: str
    deadline: str
    topic: str


@dataclass
class EvaluationResultRecord:
    id: int
    user_id: int | None
    meeting_id: int | None
    metric_name: str
    precision: float | None
    recall: float | None
    f1: float | None
    score: float | None
    notes: str
    payload_json: dict[str, Any]
    created_at: str


@dataclass
class SearchResult:
    id: int
    title: str
    meeting_date: str | None
    snippet: str
    score: float
