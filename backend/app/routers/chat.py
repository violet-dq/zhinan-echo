"""对话路由：智能体主入口 + 会话历史。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..agent.graph import run_agent
from ..database import get_db
from ..models import ChatMessage, ChatSession, User
from ..schemas import ChatIn, MessageOut
from ..security import get_current_user

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=MessageOut)
async def chat(body: ChatIn, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    """智能体对话主入口：意图识别 → 工具调度 → 回复 + 结构化卡片。"""
    session = None
    if body.session_id:
        session = db.query(ChatSession).filter_by(id=body.session_id, user_id=user.id).first()
    if session is None:
        session = ChatSession(user_id=user.id, title=body.message[:20])
        db.add(session)
        db.commit()

    history = [
        {"role": m.role, "content": m.content}
        for m in db.query(ChatMessage).filter_by(session_id=session.id)
        .order_by(ChatMessage.id.desc()).limit(8).all()
    ][::-1]

    user_msg = ChatMessage(session_id=session.id, user_id=user.id, role="user", content=body.message)
    db.add(user_msg)
    db.flush()

    result = await run_agent(db, user, body.message, history)

    assistant_msg = ChatMessage(session_id=session.id, user_id=user.id, role="assistant",
                                content=result["reply"], cards=tools_dump(result["cards"]),
                                intent=result.get("intent", ""))
    db.add(assistant_msg)
    if session.title == "新的对话":
        session.title = body.message[:20]
    db.commit()

    return MessageOut(session_id=session.id, user_message_id=user_msg.id,
                      assistant_message_id=assistant_msg.id,
                      reply=result["reply"], cards=result["cards"], intent=result.get("intent", ""))


def tools_dump(cards) -> str:
    import json
    return json.dumps(cards, ensure_ascii=False, default=str)


@router.get("/sessions")
def sessions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = (db.query(ChatSession).filter_by(user_id=user.id)
             .order_by(ChatSession.updated_at.desc()).limit(50).all())
    return [{"id": s.id, "title": s.title,
             "updated_at": s.updated_at.isoformat() if s.updated_at else ""} for s in items]


@router.get("/sessions/{session_id}/messages")
def messages(session_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter_by(id=session_id, user_id=user.id).first()
    if session is None:
        return []
    msgs = db.query(ChatMessage).filter_by(session_id=session_id).order_by(ChatMessage.id).all()
    return [{"id": m.id, "role": m.role, "content": m.content, "cards": m.cards_list(),
             "intent": m.intent, "created_at": m.created_at.isoformat() if m.created_at else ""}
            for m in msgs]
