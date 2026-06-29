from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DiscussionPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    speaker: str = Field(default="", description="Speaker name. Empty string if unknown.")
    point: str = Field(default="", description="Short discussion point from this speaker.")


class Topic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="未命名议题", description="Topic title.")
    discussion_points: list[DiscussionPoint] = Field(default_factory=list, description="Key discussion points.")
    decisions: list[str] = Field(default_factory=list, description="Decisions under this topic.")


class DecisionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner: str = Field(default="", description="Decision owner or responsible person.")
    content: str = Field(default="", description="Decision content.")
    deadline: str = Field(default="", description="Deadline if mentioned.")
    topic: str = Field(default="", description="Related topic title.")


class ActionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner: str = Field(default="", description="Responsible person.")
    task: str = Field(default="", description="Task content.")
    deadline: str = Field(default="", description="Deadline if mentioned.")
    status: Literal["待办", "进行中", "已完成", "延期", "取消"] = Field(default="待办", description="Task status.")


class MeetingMinutes(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="未命名会议", description="Meeting title or topic.")
    date: str = Field(default="", description="Meeting date.")
    time: str = Field(default="", description="Meeting time range.")
    participants: list[str] = Field(default_factory=list, description="Meeting participants.")
    summary: str = Field(default="", description="One-paragraph meeting summary.")
    topics: list[Topic] = Field(default_factory=list, description="Meeting topics.")
    decisions: list[DecisionItem] = Field(default_factory=list, description="Meeting decisions.")
    action_items: list[ActionItem] = Field(default_factory=list, description="Action items.")

    @field_validator("title")
    @classmethod
    def default_title(cls, value: str) -> str:
        return value.strip() or "未命名会议"

    @field_validator("participants")
    @classmethod
    def clean_participants(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in value:
            name = str(item).strip()
            if name and name not in seen:
                seen.add(name)
                result.append(name)
        return result
