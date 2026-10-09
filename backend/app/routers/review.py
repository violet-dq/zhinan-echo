"""复习计划路由。"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Course, Exam, ReviewTask, User
from ..schemas import ReviewPlanIn
from ..security import get_current_user
from ..services.review import create_plan, plan_progress

router = APIRouter(prefix="/api/review", tags=["review"])


def _exam_out(db: Session, exam: Exam) -> dict:
    tasks = db.query(ReviewTask).filter_by(exam_id=exam.id).order_by(ReviewTask.order_index).all()
    prog = plan_progress(exam, tasks)
    return {
        "exam_id": exam.id, "course_id": exam.course_id, "course_name": exam.course_name,
        "exam_date": exam.exam_date.strftime("%Y-%m-%d"), "progress": prog,
        "knowledge_tree": exam.tree(),
        "days": [{"task_id": t.id, "date": t.day.strftime("%Y-%m-%d"),
                  "weekday": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][t.day.weekday()],
                  "topics": t.topics_list(), "done": t.done} for t in tasks],
    }


@router.get("")
def list_exams(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    exams = db.query(Exam).filter_by(user_id=user.id).order_by(Exam.exam_date).all()
    return {"items": [_exam_out(db, e) for e in exams]}


@router.post("/plan")
async def make_plan(body: ReviewPlanIn, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    try:
        exam_date = datetime.strptime(body.exam_date, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(400, f"考试日期格式应为 YYYY-MM-DD：{exc}") from exc
    course = db.get(Course, body.course_id)
    if course is None or course.user_id != user.id:
        raise HTTPException(404, "课程不存在，请先上传该课程资料")
    if exam_date < datetime.now():
        raise HTTPException(400, "考试日期不能早于今天")
    exam = await create_plan(db, user.id, course.id, course.name or body.course_name, exam_date,
                             body.hours_per_day)
    return _exam_out(db, exam)


@router.patch("/tasks/{task_id}")
def toggle_task(task_id: int, body: dict, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    task = db.get(ReviewTask, task_id)
    if task is None or task.user_id != user.id:
        raise HTTPException(404, "任务不存在")
    task.done = bool(body.get("done", not task.done))
    db.commit()
    exam = db.get(Exam, task.exam_id)
    if body.get("reschedule", False):
        from ..services.review import reschedule_after_progress
        reschedule_after_progress(db, exam)
    return _exam_out(db, exam)


@router.delete("/{exam_id}")
def delete_plan(exam_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    exam = db.get(Exam, exam_id)
    if exam is None or exam.user_id != user.id:
        raise HTTPException(404, "计划不存在")
    db.query(ReviewTask).filter_by(exam_id=exam.id).delete()
    db.delete(exam)
    db.commit()
    return {"ok": True}
