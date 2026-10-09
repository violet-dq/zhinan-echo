"""LangGraph 智能体状态定义。"""
from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    user_id: int
    username: str
    message: str
    history: list[dict[str, str]]      # 最近多轮对话 [{role, content}]
    courses: list[dict]                # 用户课程 [{id, name}]
    intent: str
    entities: dict[str, Any]           # 意图相关的槽位（课程/标题/日期等）
    reply: str
    cards: list[dict]
    messages: list[Any]                # LangChain 消息流：承载 tool_calls / ToolMessage 的标准载体
