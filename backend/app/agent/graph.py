"""LangGraph 智能体主图。

双模式：
- LLM 模式（配置了 API Key）：load_context → llm_decision ↔ tool_node 循环 → END
  LLM 用 ChatOpenAI.bind_tools() 原生 function calling 决定调用哪个工具，支持任意自然语言
- 规则降级模式（无 API Key）：load_context → intent(正则) → route → 各 handler 节点 → END
  保留旧正则分支作 fallback，用户不填 Key 也能用（回到"特定句式"模式）
"""
import json
import logging
from typing import Callable

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Course, User
from ..services.llm import get_chat_model, llm
from . import tools
from .state import AgentState
from .tool_defs import TOOL_AGENT_SYSTEM_PROMPT, build_tools

logger = logging.getLogger("zhinan.agent")


def build_agent(db: Session, user: User):
    """构建编译后的 agent 图。db 通过闭包注入，图本身每次请求独立编译（开销极低）。"""

    # 用户自定义 LLM 配置（若设置则覆盖系统默认）
    user_settings = user.settings_dict() if hasattr(user, "settings_dict") else {}
    user_llm_key = user_settings.get("llm_api_key", "") or None
    user_llm_base = user_settings.get("llm_api_base", "") or None
    user_llm_model = user_settings.get("llm_model", "") or None
    # 用户是否启用了 LLM（有自定义 key 或系统有 key）
    user_llm_enabled = bool(user_llm_key) or settings.llm_enabled

    # ============ 共享节点 ============

    async def load_context(state: AgentState) -> dict:
        courses = [{"id": c.id, "name": c.name}
                   for c in db.query(Course).filter_by(user_id=user.id).all()]
        return {"courses": courses, "reply": "", "cards": []}

    # ============ 规则降级模式节点（无 API Key 时走这里）============

    async def intent_node(state: AgentState) -> dict:
        entities = await tools.classify_intent(state["message"], state.get("history", []),
                                               state.get("courses", []))
        logger.info("[agent] 用户=%s 意图=%s 槽位=%s", user.username, entities.get("intent"), entities)
        return {"intent": entities.get("intent", "smalltalk"), "entities": entities}

    def route(state: AgentState) -> str:
        intent = state.get("intent", "smalltalk")
        mapping = {
            "ddl_add": "ddl", "ddl_query": "ddl", "ddl_done": "ddl",
            "rag": "rag", "file_organize": "file", "file_query": "file",
            "review_plan": "review", "review_query": "review",
            "export": "export",
        }
        return mapping.get(intent, "smalltalk")

    def _handler(name: str, fn: Callable) -> Callable:
        async def node(state: AgentState) -> dict:
            try:
                return await fn(state) if _is_coroutine(fn) else fn(state)
            except Exception:  # noqa: BLE001
                logger.exception("agent 节点 %s 执行失败", name)
                return {"reply": "这一步我出了点小问题 😥 请换个说法再试一次，或稍后再来。",
                        "cards": []}
        node.__name__ = name
        return node

    def _is_coroutine(fn) -> bool:
        import inspect
        return inspect.iscoroutinefunction(fn)

    async def ddl_node(state: AgentState) -> dict:
        intent, entities = state["intent"], state.get("entities", {})
        if intent == "ddl_query":
            return tools.handle_ddl_query(db, user, state["message"])
        if intent == "ddl_done":
            return tools.handle_ddl_done(db, user, state["message"])
        return await tools.handle_ddl_add(db, user, state["message"], entities)

    async def rag_node(state: AgentState) -> dict:
        return await tools.handle_rag(db, user, state["message"], state.get("entities", {}))

    async def file_node(state: AgentState) -> dict:
        if state["intent"] == "file_query":
            return tools.handle_file_query(db, user)
        return tools.handle_file_organize(db, user, state["message"])

    async def review_node(state: AgentState) -> dict:
        if state["intent"] == "review_query":
            return tools.handle_review_query(db, user)
        return await tools.handle_review_plan(db, user, state["message"], state.get("entities", {}))

    async def smalltalk_node(state: AgentState) -> dict:
        return await tools.handle_smalltalk(db, user, state["message"], state.get("history", []))

    # ============ LLM Tool Calling 模式节点（配置了 API Key 时走这里）============

    # 预构建工具列表与 ToolNode（闭包注入 db/user）
    _tool_list = build_tools(db, user)
    _tool_by_name = {t.name: t for t in _tool_list}
    _tool_node = ToolNode(_tool_list)

    async def llm_decision_node(state: AgentState) -> dict:
        """LLM 决策节点：用 bind_tools 让 LLM 决定调用哪个工具或直接回复。"""
        chat_model = get_chat_model(
            temperature=0.3, model=user_llm_model,
            api_key=user_llm_key, api_base=user_llm_base,
        ).bind_tools(_tool_list)

        # 构建消息列表：系统提示 + 课程上下文 + 历史 + 当前用户消息
        messages = []
        courses_ctx = "、".join(c["name"] for c in state.get("courses", [])) or "（暂无课程）"
        system_content = TOOL_AGENT_SYSTEM_PROMPT + f"\n\n用户课程列表：{courses_ctx}"
        messages.append(SystemMessage(content=system_content))

        # 注入历史对话（最多 6 轮）
        for m in state.get("history", [])[-6:]:
            if m["role"] == "user":
                messages.append(HumanMessage(content=m["content"]))
            elif m["role"] == "assistant":
                messages.append(AIMessage(content=m["content"]))

        # 当前用户消息
        messages.append(HumanMessage(content=state["message"]))

        # 追加已有消息流（工具调用循环时）
        existing_msgs = state.get("messages", [])
        messages.extend(existing_msgs)

        # 调用 LLM
        ai_msg = await chat_model.ainvoke(messages)
        return {"messages": existing_msgs + [ai_msg]}

    async def tool_executor_node(state: AgentState) -> dict:
        """工具执行节点：执行 LLM 决定调用的工具，把结果回传给 LLM。"""
        last_msg = state["messages"][-1]
        tool_call_results = []
        cards_collected = state.get("cards", [])
        for tc in getattr(last_msg, "tool_calls", []) or []:
            tool_fn = _tool_by_name.get(tc["name"])
            if tool_fn is None:
                tool_call_results.append(ToolMessage(
                    content=f"未知工具：{tc['name']}", tool_call_id=tc["id"]))
                continue
            try:
                args = tc.get("args", {})
                # 统一用 ainvoke：对 async 工具会 await，对 sync 工具会在线程池执行
                result = await tool_fn.ainvoke(args)
                # result 是 {"reply":..., "cards":...} dict，转成字符串给 LLM
                result_str = json.dumps(result, ensure_ascii=False, default=str)
                tool_call_results.append(ToolMessage(content=result_str, tool_call_id=tc["id"]))
                # 收集卡片
                if isinstance(result, dict) and result.get("cards"):
                    cards_collected = cards_collected + result["cards"]
            except Exception as exc:  # noqa: BLE001
                logger.warning("工具 %s 执行失败: %s", tc["name"], exc)
                tool_call_results.append(ToolMessage(
                    content=f"工具执行出错：{exc}", tool_call_id=tc["id"]))

        return {"messages": state["messages"] + tool_call_results, "cards": cards_collected}

    async def llm_summarize_node(state: AgentState) -> dict:
        """工具执行后，让 LLM 生成自然语言总结回复给用户。"""
        chat_model = get_chat_model(
            temperature=0.3, model=user_llm_model,
            api_key=user_llm_key, api_base=user_llm_base,
        )
        courses_ctx = "、".join(c["name"] for c in state.get("courses", [])) or "（暂无课程）"
        system_content = (TOOL_AGENT_SYSTEM_PROMPT + f"\n\n用户课程列表：{courses_ctx}\n"
                          "工具已执行完毕，请根据工具返回的结果，用简洁亲切的中文总结给用户。"
                          "不要原样照搬 JSON，要像朋友对话一样自然。")
        messages = [SystemMessage(content=system_content)] + state.get("messages", [])
        ai_msg = await chat_model.ainvoke(messages)
        reply = getattr(ai_msg, "content", "") or ""
        # 如果还有 tool_calls（罕见，工具又触发了新调用），追加但不处理
        return {"reply": reply, "messages": state.get("messages", []) + [ai_msg]}

    def has_tool_calls(state: AgentState) -> str:
        """路由：LLM 输出含 tool_calls → tool_executor；否则 → summarize。"""
        msgs = state.get("messages", [])
        if not msgs:
            return END
        last = msgs[-1]
        if getattr(last, "tool_calls", None):
            return "tool_executor"
        # 工具已执行完，且 LLM 没再调工具 → 直接用工具结果里的 reply（首次无工具调用也走这里）
        return "summarize"

    def needs_summarize(state: AgentState) -> str:
        """工具执行后：回到 llm_decision 让 LLM 总结，或若首次 LLM 直接回复无工具调用则结束。"""
        # 工具结果已在 messages 里，让 LLM 总结
        return "llm_decision"

    # ============ 图构建 ============

    builder = StateGraph(AgentState)

    # 共享节点
    builder.add_node("load_context", _handler("load_context", load_context))

    # LLM 模式节点
    builder.add_node("llm_decision", _handler("llm_decision", llm_decision_node))
    builder.add_node("tool_executor", _handler("tool_executor", tool_executor_node))
    builder.add_node("summarize", _handler("summarize", llm_summarize_node))

    # 规则降级模式节点
    builder.add_node("intent", _handler("intent", intent_node))
    builder.add_node("ddl", _handler("ddl", ddl_node))
    builder.add_node("rag", _handler("rag", rag_node))
    builder.add_node("file", _handler("file", file_node))
    builder.add_node("review", _handler("review", review_node))
    builder.add_node("export", _handler("export", tools.handle_export))
    builder.add_node("smalltalk", _handler("smalltalk", smalltalk_node))

    # 入口：根据用户级 llm_enabled 分流
    builder.add_edge(START, "load_context")
    builder.add_conditional_edges(
        "load_context",
        lambda s: "llm_decision" if user_llm_enabled else "intent",
        {"llm_decision": "llm_decision", "intent": "intent"},
    )

    # LLM 模式：llm_decision ↔ tool_executor 循环 → summarize → END
    builder.add_conditional_edges(
        "llm_decision",
        has_tool_calls,
        {"tool_executor": "tool_executor", "summarize": "summarize", END: END},
    )
    builder.add_edge("tool_executor", "llm_decision")
    builder.add_edge("summarize", END)

    # 规则模式：intent → route → 各节点 → END
    node_names = ["ddl", "rag", "file", "review", "export", "smalltalk"]
    builder.add_conditional_edges("intent", route, {n: n for n in node_names})
    for node in node_names:
        builder.add_edge(node, END)

    return builder.compile()


async def run_agent(db: Session, user: User, message: str, history: list[dict]) -> dict:
    """运行智能体，返回 {"reply": str, "cards": [...], "intent": str}。"""
    agent = build_agent(db, user)
    initial_state: AgentState = {
        "user_id": user.id, "username": user.nickname or user.username,
        "message": message, "history": history, "intent": "", "entities": {},
        "reply": "", "cards": [], "messages": [],
    }
    result = await agent.ainvoke(initial_state)

    # LLM 模式下，cards 可能在 tool_executor 节点累积；规则模式下 cards 在各节点返回
    reply = result.get("reply", "")
    cards = result.get("cards", [])

    # LLM 模式且没经过 summarize（直接回复无工具调用）：从最后一条 AIMessage 取 content
    if not reply and result.get("messages"):
        last = result["messages"][-1]
        reply = getattr(last, "content", "") or ""

    # 若工具执行累积了 cards 但 reply 为空，用工具返回的 reply
    if not reply and cards:
        for c in cards:
            # 工具结果里可能没 reply 字段，兜底
            pass

    user_settings = user.settings_dict() if hasattr(user, "settings_dict") else {}
    user_llm_key = user_settings.get("llm_api_key", "") or None
    user_llm_enabled = bool(user_llm_key) or settings.llm_enabled
    intent_label = "tool_call" if user_llm_enabled else result.get("intent", "")
    return {"reply": reply, "cards": cards, "intent": intent_label}
