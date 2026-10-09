"""用户认证路由。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import LoginIn, RegisterIn, TokenOut
from ..security import create_token, get_current_user, hash_password, verify_password
from ..config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if db.query(User).filter_by(username=body.username).first():
        raise HTTPException(400, "用户名已被注册")
    user = User(username=body.username, password_hash=hash_password(body.password),
                nickname=body.nickname or body.username, email=body.email)
    db.add(user)
    db.commit()
    return TokenOut(token=create_token(user.id), nickname=user.nickname,
                    llm_enabled=settings.llm_enabled, embedding_enabled=settings.embedding_enabled)


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(username=body.username).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "用户名或密码错误")
    return TokenOut(token=create_token(user.id), nickname=user.nickname,
                    llm_enabled=settings.llm_enabled, embedding_enabled=settings.embedding_enabled)


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    s = user.settings_dict() if hasattr(user, "settings_dict") else {}
    user_llm_enabled = bool(s.get("llm_api_key")) or settings.llm_enabled
    return {
        "id": user.id, "username": user.username, "nickname": user.nickname,
        "avatar": user.avatar,
        "llm_enabled": user_llm_enabled, "embedding_enabled": settings.embedding_enabled,
    }
