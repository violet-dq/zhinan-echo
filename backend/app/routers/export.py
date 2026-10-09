"""导出中心：iCal / CSV / Markdown。"""
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import DDL, DocumentFile, Exam, ReviewTask, User
from ..security import get_current_user
from ..services.exporter import (export_ddl_ics, export_files_csv,
                                 export_files_markdown, export_review_markdown)

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/ddl.ics", response_class=PlainTextResponse)
def ddl_ics(status: str = "pending", user: User = Depends(get_current_user),
            db: Session = Depends(get_db)):
    q = db.query(DDL).filter(DDL.user_id == user.id)
    if status != "all":
        q = q.filter(DDL.status == status)
    content = export_ddl_ics(q.order_by(DDL.due_at).all())
    return PlainTextResponse(content, media_type="text/calendar; charset=utf-8",
                             headers={"Content-Disposition":
                                      'attachment; filename="zhinan-echo-ddl.ics"'})


@router.get("/files.csv")
def files_csv(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    files = db.query(DocumentFile).filter_by(user_id=user.id).order_by(DocumentFile.created_at.desc()).all()
    return PlainTextResponse("\ufeff" + export_files_csv(files),
                             media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition":
                                      'attachment; filename="zhinan-echo-files.csv"'})


@router.get("/files.md")
def files_md(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    files = db.query(DocumentFile).filter_by(user_id=user.id).order_by(DocumentFile.created_at.desc()).all()
    return PlainTextResponse(export_files_markdown(files), media_type="text/markdown; charset=utf-8",
                             headers={"Content-Disposition":
                                      'attachment; filename="zhinan-echo-files.md"'})


@router.get("/review-{exam_id}.md")
def review_md(exam_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    exam = db.get(Exam, exam_id)
    if exam is None or exam.user_id != user.id:
        exam = None
    tasks = db.query(ReviewTask).filter_by(exam_id=exam_id).order_by(ReviewTask.order_index).all() \
        if exam else []
    content = export_review_markdown(exam, tasks)
    name = f"{exam.course_name}-复习计划.md" if exam else "复习计划.md"
    return PlainTextResponse(content, media_type="text/markdown; charset=utf-8",
                             headers={"Content-Disposition":
                                      f'attachment; filename="{name}"'})


@router.get("/review-print")
def review_print(exam_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """可打印 HTML（浏览器打印为 PDF）。"""
    exam = db.get(Exam, exam_id)
    if exam is None or exam.user_id != user.id:
        return PlainTextResponse("计划不存在", status_code=404)
    tasks = db.query(ReviewTask).filter_by(exam_id=exam_id).order_by(ReviewTask.order_index).all()
    md = export_review_markdown(exam, tasks)
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>{exam.course_name} 复习计划</title>
<style>body{{font-family:"PingFang SC","Microsoft YaHei",serif;max-width:760px;margin:40px auto;
line-height:1.8;color:#333;padding:0 20px}}h1{{color:#7B4B9A}}h2{{border-bottom:2px solid #E8D5F0;
padding-bottom:4px;color:#5a3a75}}</style></head>
<body><pre style="white-space:pre-wrap;font-family:inherit;font-size:15px">{md}</pre>
<script>window.print&&setTimeout(()=>window.print(),500)</script></body></html>"""
    from fastapi.responses import HTMLResponse
    return HTMLResponse(html)
