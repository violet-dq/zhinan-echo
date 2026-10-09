"""Pydantic 请求/响应模型。"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class RegisterIn(BaseModel):
    username: str = Field(min_length=2, max_length=32)
    password: str = Field(min_length=6, max_length=64)
    nickname: str = ""
    email: str = ""


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    token: str
    nickname: str
    llm_enabled: bool
    embedding_enabled: bool


class ChatIn(BaseModel):
    session_id: Optional[int] = None
    message: str = Field(min_length=1, max_length=8000)


class Card(BaseModel):
    type: str                                   # ddl_list / ddl_added / files / review_plan / notice
    data: dict[str, Any] = {}


class MessageOut(BaseModel):
    session_id: int
    user_message_id: int
    assistant_message_id: int
    reply: str
    cards: list[dict] = []
    intent: str = ""


class DDLIn(BaseModel):
    title: str
    detail: str = ""
    due_at: datetime
    course_id: Optional[int] = None
    priority: str = "medium"


class DDLOut(BaseModel):
    id: int
    title: str
    detail: str
    due_at: datetime
    course_id: Optional[int]
    course_name: str = ""
    priority: str
    status: str
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DDLExtractIn(BaseModel):
    text: str = Field(min_length=2, max_length=20000)


class FileRenameIn(BaseModel):
    course_id: Optional[int] = None
    tags: Optional[dict] = None


class ReviewPlanIn(BaseModel):
    course_id: int
    course_name: str = ""
    exam_date: str                             # YYYY-MM-DD
    hours_per_day: float = 2.0


class ReviewTaskDoneIn(BaseModel):
    done: bool
