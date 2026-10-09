"""用户资料与设置路由：头像/昵称/邮箱、改密码、皮肤/字体/下载路径/通知/LLM API Key。"""
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user, hash_password, verify_password

router = APIRouter(prefix="/api/user", tags=["user"])

# 用户偏好的默认值
DEFAULT_SETTINGS = {
    "theme": "echo",            # echo(二月兰) / light(白色) / dark(黑色) / summer(夏季暖阳) / winter(冬季雪花)
    "font_size": "medium",      # small / medium / large / xlarge
    "download_path": "",        # 浏览器端下载路径提示（实际下载由浏览器决定）
    "notify_ddl": True,         # DDL 主动提醒开关
    "notify_sound": True,       # 通知声音
    "llm_api_base": "",         # 用户自定义 LLM API Base（留空用系统默认）
    "llm_api_key": "",          # 用户自定义 LLM API Key（留空用系统默认）
    "llm_model": "",            # 用户自定义模型名
}


def _merge_settings(user: User) -> dict:
    """合并用户设置与默认值。"""
    s = user.settings_dict()
    merged = {**DEFAULT_SETTINGS, **s}
    return merged


@router.get("/profile")
def get_profile(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "username": user.username,
        "nickname": user.nickname,
        "email": user.email,
        "avatar": user.avatar,
        "created_at": user.created_at.isoformat() if user.created_at else "",
    }


@router.patch("/profile")
def update_profile(body: dict, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    nickname = (body.get("nickname") or "").strip()
    email = (body.get("email") or "").strip()
    avatar = body.get("avatar") or ""
    if nickname:
        user.nickname = nickname[:32]
    if email:
        user.email = email[:128]
    if avatar:
        # 限制 base64 头像大小（约 500KB）
        if len(avatar) > 700000:
            raise HTTPException(400, "头像过大，请使用更小的图片")
        user.avatar = avatar
    db.commit()
    return {"ok": True, "nickname": user.nickname, "avatar": user.avatar, "email": user.email}


@router.post("/password")
def change_password(body: dict, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    old_pw = body.get("old_password") or ""
    new_pw = body.get("new_password") or ""
    if not old_pw or not new_pw:
        raise HTTPException(400, "原密码和新密码不能为空")
    if not verify_password(old_pw, user.password_hash):
        raise HTTPException(401, "原密码不正确")
    if len(new_pw) < 6:
        raise HTTPException(400, "新密码至少 6 位")
    user.password_hash = hash_password(new_pw)
    db.commit()
    return {"ok": True}


@router.get("/settings")
def get_settings(user: User = Depends(get_current_user)):
    s = _merge_settings(user)
    # 不把 API key 明文回传给前端（用掩码表示是否已设置）
    s["llm_api_key_set"] = bool(s.get("llm_api_key"))
    s["llm_api_key"] = ""
    return s


@router.patch("/settings")
def update_settings(body: dict, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    merged = _merge_settings(user)
    allowed = set(DEFAULT_SETTINGS.keys())
    for k, v in body.items():
        if k in allowed:
            merged[k] = v
    # API key 特殊处理：传空字符串表示清除，传非空表示设置
    if "llm_api_key" in body:
        merged["llm_api_key"] = body["llm_api_key"] or ""
    user.settings = json.dumps(merged, ensure_ascii=False)
    db.commit()
    return {"ok": True, "settings": _merge_settings(user)}
