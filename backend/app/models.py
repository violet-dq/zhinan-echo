"""数据模型：用户、课程、资料、DDL、复习计划、对话、通知。"""
import json
from datetime import datetime

from sqlalchemy import (JSON, Boolean, DateTime, Float, ForeignKey, Integer,
                        Text)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def now_local() -> datetime:
    """全系统统一使用本地时区的 naive datetime（比赛部署环境即北京时间）。"""
    return datetime.now()


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(default="", server_default="")
    nickname: Mapped[str] = mapped_column(default="", server_default="")
    avatar: Mapped[str] = mapped_column(Text, default="", server_default="")   # 头像 base64 data URI 或颜色
    settings: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")  # 用户偏好 JSON
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)

    courses: Mapped[list["Course"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    def settings_dict(self) -> dict:
        try:
            return json.loads(self.settings or "{}")
        except json.JSONDecodeError:
            return {}


class Course(Base):
    """课程目录：资料与 DDL 的归档维度。"""
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(index=True)
    color: Mapped[str] = mapped_column(default="#7B4B9A")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)

    user: Mapped[User] = relationship(back_populates="courses")
    files: Mapped[list["DocumentFile"]] = relationship(back_populates="course", cascade="all, delete-orphan")


class DocumentFile(Base):
    """学习资料：原文入库 + 自动标签 + 分块向量化。"""
    __tablename__ = "files"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id"), nullable=True)
    filename: Mapped[str] = mapped_column(Text)
    file_type: Mapped[str] = mapped_column(default="")           # pdf/docx/pptx/txt/md/img
    size: Mapped[int] = mapped_column(Integer, default=0)
    stored_path: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[str] = mapped_column(Text, default="")        # 解析出的全文
    outline: Mapped[str] = mapped_column(Text, default="[]")      # 章节结构 JSON
    tags: Mapped[str] = mapped_column(Text, default="{}")         # {course,type,sections,keywords}
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(default="ready")          # parsing/ready/failed
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)

    course: Mapped[Course | None] = relationship(back_populates="files")

    def tags_dict(self) -> dict:
        try:
            return json.loads(self.tags or "{}")
        except json.JSONDecodeError:
            return {}

    def outline_list(self) -> list:
        try:
            return json.loads(self.outline or "[]")
        except json.JSONDecodeError:
            return []


class Chunk(Base):
    """文档分块：向量检索与 BM25 检索的粒度单位。"""
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text)
    page: Mapped[int] = mapped_column(Integer, default=0)
    section: Mapped[str] = mapped_column(default="", server_default="")
    bm25_tokens: Mapped[str] = mapped_column(Text, default="")    # 预分词结果


class DDL(Base):
    """截止任务：对话/OCR/文本提取/文件名解析四种来源。"""
    __tablename__ = "ddls"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id"), nullable=True)
    title: Mapped[str] = mapped_column(Text)
    detail: Mapped[str] = mapped_column(Text, default="")
    due_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    priority: Mapped[str] = mapped_column(default="medium")       # high/medium/low
    status: Mapped[str] = mapped_column(default="pending")        # pending/done
    source: Mapped[str] = mapped_column(default="chat")           # chat/ocr/text/filename
    reminded: Mapped[str] = mapped_column(Text, default="[]")     # 已发送提醒的档位
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)

    course_ref: Mapped["Course | None"] = relationship(foreign_keys=[course_id])

    @property
    def course(self):
        return self.course_ref

    def reminded_list(self) -> list:
        try:
            return json.loads(self.reminded or "[]")
        except json.JSONDecodeError:
            return []


class Exam(Base):
    """复习规划：一场考试对应一棵知识树与一份每日计划。"""
    __tablename__ = "exams"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id"), nullable=True)
    course_name: Mapped[str] = mapped_column(default="")
    exam_date: Mapped[str] = mapped_column(DateTime)
    knowledge_tree: Mapped[str] = mapped_column(Text, default="[]")  # [{chapter,sections:[{name,points:[..]}]}]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)

    tasks: Mapped[list["ReviewTask"]] = relationship(back_populates="exam", cascade="all, delete-orphan")

    def tree(self) -> list:
        try:
            return json.loads(self.knowledge_tree or "[]")
        except json.JSONDecodeError:
            return []


class ReviewTask(Base):
    """每日复习任务。"""
    __tablename__ = "review_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id"), index=True)
    day: Mapped[str] = mapped_column(DateTime)     # 计划归属日期
    topics: Mapped[str] = mapped_column(Text, default="[]")       # 当日知识点
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str] = mapped_column(Text, default="")
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    exam: Mapped[Exam] = relationship(back_populates="tasks")

    def topics_list(self) -> list:
        try:
            return json.loads(self.topics or "[]")
        except json.JSONDecodeError:
            return []


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(default="新的对话")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_local, onupdate=now_local)


class ChatMessage(Base):
    """对话历史：cards 字段存放结构化卡片（DDL列表/资料卡片/复习计划等）。"""
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(default="user")             # user/assistant
    content: Mapped[str] = mapped_column(Text, default="")
    cards: Mapped[str] = mapped_column(Text, default="[]")
    intent: Mapped[str] = mapped_column(default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)

    def cards_list(self) -> list:
        try:
            return json.loads(self.cards or "[]")
        except json.JSONDecodeError:
            return []


class Notification(Base):
    """站内提醒：DDL 的 7天/3天/1天/1小时 主动推送。"""
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    ddl_id: Mapped[int | None] = mapped_column(ForeignKey("ddls.id"), nullable=True)
    level: Mapped[str] = mapped_column(default="info")            # info/warning/urgent
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text, default="")
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)
