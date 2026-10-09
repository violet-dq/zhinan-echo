"""课程与通知路由。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Course, DocumentFile, Notification, User
from ..security import get_current_user

router = APIRouter(prefix="/api", tags=["misc"])


# ---------- 课程 ----------

@router.get("/courses")
def list_courses(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    courses = db.query(Course).filter_by(user_id=user.id).order_by(Course.created_at).all()
    items = []
    for c in courses:
        cnt = db.query(DocumentFile).filter_by(course_id=c.id).count()
        items.append({"id": c.id, "name": c.name, "color": c.color, "file_count": cnt})
    return {"items": items}


@router.post("/courses")
def create_course(body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "课程名不能为空")
    if db.query(Course).filter_by(user_id=user.id, name=name).first():
        raise HTTPException(400, "课程已存在")
    course = Course(user_id=user.id, name=name, color=body.get("color", "#7B4B9A"))
    db.add(course)
    db.commit()
    return {"id": course.id, "name": course.name, "color": course.color, "file_count": 0}


@router.delete("/courses/{course_id}")
def delete_course(course_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    course = db.get(Course, course_id)
    if course is None or course.user_id != user.id:
        raise HTTPException(404, "课程不存在")
    if db.query(DocumentFile).filter_by(course_id=course.id).count():
        raise HTTPException(400, "该课程下仍有资料，请先移除或转移资料")
    db.delete(course)
    db.commit()
    return {"ok": True}


# ---------- 通知（DDL 主动提醒） ----------

@router.get("/notifications")
def list_notifications(only_unread: bool = False, user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    q = db.query(Notification).filter_by(user_id=user.id)
    if only_unread:
        q = q.filter_by(read=False)
    items = q.order_by(Notification.id.desc()).limit(50).all()
    dicts = [{
        "id": n.id, "level": n.level, "title": n.title, "body": n.body, "read": n.read,
        "ddl_id": n.ddl_id, "created_at": n.created_at.isoformat() if n.created_at else "",
    } for n in items]
    return {"items": dicts, "unread": sum(1 for i in dicts if not i["read"])}


@router.post("/notifications/read")
def mark_read(body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.get("all"):
        db.query(Notification).filter_by(user_id=user.id, read=False).update({"read": True})
    elif body.get("id"):
        n = db.get(Notification, body["id"])
        if n and n.user_id == user.id:
            n.read = True
    db.commit()
    return {"ok": True}


# ---------- 仪表盘快捷卡片 ----------

@router.get("/dashboard")
def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from datetime import datetime, timedelta
    from ..models import DDL, Exam, ReviewTask
    now = datetime.now()
    pending = db.query(DDL).filter(DDL.user_id == user.id, DDL.status == "pending").order_by(DDL.due_at).all()
    today = [d for d in pending if d.due_at.date() == now.date()]
    week = [d for d in pending if now.date() < d.due_at.date() <= (now + timedelta(days=7)).date()]
    files_cnt = db.query(DocumentFile).filter_by(user_id=user.id).count()
    exams = db.query(Exam).filter(Exam.user_id == user.id, Exam.exam_date >= now.date()).order_by(Exam.exam_date).all()
    review_summary = []
    for e in exams[:2]:
        tasks = db.query(ReviewTask).filter_by(exam_id=e.id).all()
        total = sum(len(t.topics_list()) for t in tasks)
        done = sum(len(t.topics_list()) for t in tasks if t.done)
        today_task = next((t for t in sorted(tasks, key=lambda x: x.order_index)
                           if t.day.date() == now.date()), None)
        review_summary.append({
            "exam_id": e.id, "course_name": e.course_name,
            "exam_date": e.exam_date.strftime("%m-%d"),
            "days_to_exam": (e.exam_date.date() - now.date()).days,
            "percent": round(done * 100 / total, 1) if total else 0,
            "today_topics": [p.get("point", "") for p in today_task.topics_list()][:5] if today_task else [],
        })
    recent_files = db.query(DocumentFile).filter_by(user_id=user.id) \
        .order_by(DocumentFile.created_at.desc()).limit(3).all()
    return {
        "today_ddl": [{"id": d.id, "title": d.title, "due_at": d.due_at.strftime("%H:%M"),
                       "priority": d.priority} for d in today],
        "week_ddl_count": len(week),
        "files_count": files_cnt,
        "reviews": review_summary,
        "recent_files": [{"id": f.id, "filename": f.filename,
                           "course": f.course.name if f.course else "未分类"} for f in recent_files],
    }
