"""资料库路由：批量上传（自动解析+标签+向量化）、列表、更新、删除、预览、下载。"""
import os
import shutil
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import DocumentFile, User
from ..security import get_current_user
from ..services.ingest import SUPPORTED, filename_ddl_hint, ingest_file, reindex_file
from ..services.parser import SUPPORTED_EXT

router = APIRouter(prefix="/api/files", tags=["files"])

# 文件扩展名 → MIME 类型映射（用于预览/下载响应头）
_EXT_MIME = {
    "pdf": "application/pdf",
    "txt": "text/plain; charset=utf-8",
    "md": "text/markdown; charset=utf-8",
    "markdown": "text/markdown; charset=utf-8",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
}


def _mime_of(filename: str) -> str:
    ext = os.path.splitext(filename or "")[1].lower().lstrip(".")
    return _EXT_MIME.get(ext, "application/octet-stream")


def _file_out(f: DocumentFile) -> dict:
    tags = f.tags_dict()
    return {
        "id": f.id, "filename": f.filename, "file_type": f.file_type,
        "size": f.size, "course_id": f.course_id,
        "course": f.course.name if f.course else "未分类",
        "type": tags.get("type", ""), "keywords": tags.get("keywords", []),
        "sections": tags.get("sections", []), "outline": f.outline_list(),
        "chunk_count": f.chunk_count, "status": f.status, "error": f.error,
        "created_at": f.created_at.isoformat() if f.created_at else "",
        "content_preview": (f.content[:500] + "…") if len(f.content) > 500 else f.content,
        "has_file": bool(f.stored_path and os.path.exists(f.stored_path)),
        "mime": _mime_of(f.filename),
    }


@router.post("/upload")
async def upload(files: list[UploadFile] = File(...), user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    """批量上传：解析→自动标签→分块→向量化，返回逐文件结果。"""
    results = []
    for f in files:
        ext = os.path.splitext(f.filename or "")[1].lower()
        if ext not in SUPPORTED_EXT:
            results.append({"filename": f.filename, "ok": False,
                            "error": f"暂不支持的格式 {ext or '(无扩展名)'}，支持 PDF/Word/PPT/TXT/MD/图片"})
            continue
        dest_dir = os.path.join(settings.data_dir, "uploads", str(user.id))
        os.makedirs(dest_dir, exist_ok=True)
        stored = os.path.join(dest_dir, f"{uuid.uuid4().hex}{ext}")
        try:
            with open(stored, "wb") as out:
                shutil.copyfileobj(f.file, out)
        finally:
            await f.close()
        if os.path.getsize(stored) > settings.max_upload_mb * 1024 * 1024:
            os.unlink(stored)
            results.append({"filename": f.filename, "ok": False,
                            "error": f"文件超过 {settings.max_upload_mb}MB 限制"})
            continue
        try:
            doc = await ingest_file(db, user.id, stored, f.filename)
            message = "已解析并完成自动归档"
            # 文件名日期识别：如「算法作业-0820截止.pdf」自动创建 DDL
            hint_title, hint_due = filename_ddl_hint(f.filename)
            if hint_due:
                from ..models import DDL
                ddl = DDL(user_id=user.id, course_id=doc.course_id,
                          title=hint_title, detail=f"由文件名自动识别：{f.filename}",
                          due_at=hint_due, priority="medium", source="filename")
                db.add(ddl)
                db.commit()
                message += f"；识别到截止日期 {hint_due.strftime('%m月%d日')}，已自动创建提醒任务 ⏰"
            results.append({"filename": f.filename, "ok": True, "file": _file_out(doc),
                            "message": message})
        except ValueError as exc:
            if os.path.exists(stored):
                os.unlink(stored)
            results.append({"filename": f.filename, "ok": False, "error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            if os.path.exists(stored):
                os.unlink(stored)
            results.append({"filename": f.filename, "ok": False, "error": f"入库失败：{exc}"})
    return {"results": results,
            "succeeded": sum(1 for r in results if r["ok"]),
            "failed": sum(1 for r in results if not r["ok"])}


@router.get("")
def list_files(course_id: int | None = None, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    q = db.query(DocumentFile).filter_by(user_id=user.id)
    if course_id:
        q = q.filter_by(course_id=course_id)
    files = q.order_by(DocumentFile.created_at.desc()).all()
    return {"items": [_file_out(f) for f in files], "total": len(files)}


def _get_owned_file(file_id: int, user: User, db: Session) -> DocumentFile:
    f = db.get(DocumentFile, file_id)
    if f is None or f.user_id != user.id:
        raise HTTPException(404, "文件不存在")
    if not f.stored_path or not os.path.exists(f.stored_path):
        raise HTTPException(404, "原始文件不存在（可能已被清理）")
    return f


@router.get("/{file_id}/preview")
def preview_file(file_id: int, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    """在线预览：以 inline 方式返回原始文件，浏览器内嵌渲染（PDF/图片直接显示）。
    不传 filename 让 FileResponse 不附加 Content-Disposition，浏览器用 inline 默认行为。"""
    f = _get_owned_file(file_id, user, db)
    return FileResponse(f.stored_path, media_type=_mime_of(f.filename))


@router.get("/{file_id}/download")
def download_file(file_id: int, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    """下载原始文件：filename 参数让 FileResponse 自动用 RFC 5987 的
    filename*=utf-8''... 形式处理非 ASCII 文件名，避免 latin-1 编码错误。"""
    f = _get_owned_file(file_id, user, db)
    return FileResponse(f.stored_path, media_type=_mime_of(f.filename),
                        filename=f.filename)


@router.get("/{file_id}")
def file_detail(file_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    f = db.get(DocumentFile, file_id)
    if f is None or f.user_id != user.id:
        raise HTTPException(404, "文件不存在")
    out = _file_out(f)
    out["content"] = f.content
    return out


@router.patch("/{file_id}")
async def update_file(file_id: int, body: dict, user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    """修改归档（课程/标签），并同步重建索引。"""
    f = db.get(DocumentFile, file_id)
    if f is None or f.user_id != user.id:
        raise HTTPException(404, "文件不存在")
    if "course_id" in body or "course_name" in body:
        from ..models import Course
        name = body.get("course_name", "")
        cid = body.get("course_id")
        if name:
            course = db.query(Course).filter_by(user_id=user.id, name=name).first()
            if course is None:
                course = Course(user_id=user.id, name=name)
                db.add(course)
                db.flush()
            f.course_id = course.id
        elif cid is not None:
            f.course_id = cid or None
    if "tags" in body and isinstance(body["tags"], dict):
        import json
        tags = f.tags_dict()
        tags.update(body["tags"])
        f.tags = json.dumps(tags, ensure_ascii=False)
    db.commit()
    await reindex_file(db, f)
    return _file_out(f)


@router.delete("/{file_id}")
def delete_file(file_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from ..models import Chunk
    from ..services.vector_store import vector_store
    f = db.get(DocumentFile, file_id)
    if f is None or f.user_id != user.id:
        raise HTTPException(404, "文件不存在")
    db.query(Chunk).filter_by(file_id=f.id).delete()
    vector_store.remove_file(user.id, f.id)
    if f.stored_path and os.path.exists(f.stored_path):
        os.unlink(f.stored_path)
    db.delete(f)
    db.commit()
    return {"ok": True}
