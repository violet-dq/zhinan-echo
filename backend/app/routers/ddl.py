"""DDL 路由：CRUD + 文本批量提取 + 截图 OCR 识别。"""
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..agent.tools import extract_ddls_from_text, query_ddls
from ..database import get_db
from ..models import DDL, User
from ..schemas import DDLExtractIn, DDLIn
from ..security import get_current_user
from ..services.dateparse import relative_days_phrase

router = APIRouter(prefix="/api/ddl", tags=["ddl"])


def _out(d: DDL) -> dict:
    return {
        "id": d.id, "title": d.title, "detail": d.detail,
        "due_at": d.due_at.isoformat(), "course_id": d.course_id,
        "course": d.course.name if d.course else "", "priority": d.priority,
        "status": d.status, "source": d.source,
        "days_left": (d.due_at.date() - datetime.now().date()).days,
        "relative": relative_days_phrase(d.due_at),
        "created_at": d.created_at.isoformat() if d.created_at else "",
    }


@router.get("")
def list_ddl(status: str = "pending", user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    q = db.query(DDL).filter(DDL.user_id == user.id)
    if status != "all":
        q = q.filter(DDL.status == status)
    return {"items": [_out(d) for d in q.order_by(DDL.due_at).all()]}


def _naive_local(dt: datetime) -> datetime:
    """归一化时间：带时区的转本地后去掉 tzinfo，与库内 naive local 时间统一。"""
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    return dt


def _parse_any(value) -> datetime | None:
    """兼容 ISO 字符串（含 Z 后缀）与 datetime，失败返回 None。"""
    if isinstance(value, datetime):
        return _naive_local(value)
    try:
        return _naive_local(datetime.fromisoformat(str(value).replace("Z", "+00:00")))
    except ValueError:
        return None


@router.post("")
def create_ddl(body: DDLIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    due = _naive_local(body.due_at)
    if due < datetime(2000, 1, 1):
        raise HTTPException(400, "截止时间无效")
    ddl = DDL(user_id=user.id, course_id=body.course_id, title=body.title,
              detail=body.detail, due_at=due, priority=body.priority, source="manual")
    db.add(ddl)
    db.commit()
    return _out(ddl)


@router.patch("/{ddl_id}")
def update_ddl(ddl_id: int, body: dict, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    ddl = db.get(DDL, ddl_id)
    if ddl is None or ddl.user_id != user.id:
        raise HTTPException(404, "任务不存在")
    for field in ("title", "detail", "priority", "status"):
        if field in body:
            setattr(ddl, field, body[field])
    if "due_at" in body:
        parsed = _parse_any(body["due_at"])
        if parsed is None:
            raise HTTPException(400, "时间格式错误，应为 ISO 格式（如 2026-08-20T22:00）")
        ddl.due_at = parsed
    if "course_id" in body:
        ddl.course_id = body["course_id"] or None
    db.commit()
    return _out(ddl)


@router.delete("/{ddl_id}")
def delete_ddl(ddl_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ddl = db.get(DDL, ddl_id)
    if ddl is None or ddl.user_id != user.id:
        raise HTTPException(404, "任务不存在")
    db.delete(ddl)
    db.commit()
    return {"ok": True}


@router.post("/extract")
async def extract(body: DDLExtractIn, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    """粘贴通知文字，自动识别其中所有 DDL。"""
    ddls = await extract_ddls_from_text(db, user, body.text)
    return {"items": [_out(d) for d in ddls],
            "count": len(ddls),
            "message": f"识别到 {len(ddls)} 条截止任务" if ddls else "未识别到包含截止时间的任务，请确认文字中包含日期"}


@router.post("/ocr")
async def ocr_ddl(image: UploadFile = File(...), user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    """上传群通知截图 → OCR → 提取 DDL。"""
    import os
    import shutil
    import tempfile
    ext = os.path.splitext(image.filename or "")[1].lower()
    if ext not in (".jpg", ".jpeg", ".png"):
        raise HTTPException(400, "请上传 JPG/PNG 图片")
    try:
        from ..services.parser import _run_ocr_image
    except ImportError:
        raise HTTPException(501, "服务器未安装 OCR 引擎（paddleocr），请先安装：pip install paddleocr paddlepaddle")
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        shutil.copyfileobj(image.file, tmp)
        path = tmp.name
    try:
        text = _run_ocr_image(path)
    finally:
        os.unlink(path)
    if not text.strip():
        return {"ocr_text": "", "items": [], "message": "图片中未识别到文字"}
    ddls = await extract_ddls_from_text(db, user, text)
    return {"ocr_text": text[:1000], "items": [_out(d) for d in ddls],
            "count": len(ddls), "message": f"OCR 完成，识别到 {len(ddls)} 条截止任务"}
