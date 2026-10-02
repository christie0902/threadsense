from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Role(str, Enum):
    ENGINEER = "ENGINEER"
    TEAM_LEAD = "TEAM_LEAD"
    QA_TUTOR = "QA_TUTOR"
    TUTOR = "TUTOR"


class ChannelType(str, Enum):
    GENERAL = "GENERAL"
    QA = "QA"
    ANNOUNCEMENTS = "ANNOUNCEMENTS"


class MessageSource(str, Enum):
    USER = "USER"
    WORKFLOW = "WORKFLOW"
    BOT = "BOT"


class Message(BaseModel):
    message_id: str

    author_id: str
    author_name: str
    author_role: Role

    timestamp: datetime
    text: str

    source: MessageSource = MessageSource.USER
    reactions: list[str] = Field(default_factory=list)


class Thread(BaseModel):
    thread_id: str

    project_id: str
    channel_id: str
    channel_name: str
    channel_type: ChannelType

    language: str | None = None

    created_at: datetime
    messages: list[Message]

    @property
    def message_count(self) -> int:
        return len(self.messages)