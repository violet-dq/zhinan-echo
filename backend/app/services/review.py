"""复习规划：知识树提取（LLM/章节降级）+ 按剩余天数智能排期 + 进度驱动重排。"""
import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from ..models import DocumentFile, Exam, ReviewTask
from .llm import llm


async def build_knowledge_tree(db: Session, user_id: int, course_id: int, course_name: str) -> list[dict]:
    """从课程资料提取知识树 [{chapter, sections:[{name, points:[...]}]}]。"""
    files = db.query(DocumentFile).filter_by(user_id=user_id, course_id=course_id).all()
    outlines = []
    for f in files:
        for o in f.outline_list():
            outlines.append(o.get("title", ""))
    outline_text = "\n".join(outlines[:60])
    sample = ""
    for f in files[:3]:
        sample += f"【{f.filename}】\n{f.content[:800]}\n"

    if llm.enabled:
        result = await llm.chat_json(
            f"课程：{course_name}\n该课程资料目录中的章节结构：\n{outline_text}\n\n资料摘录：\n{sample}\n\n"
            "请基于以上资料总结这门课的知识树，用于考前复习。输出 JSON："
            '{"tree":[{"chapter":"第1章 绪论","sections":[{"name":"基本概念","points":["知识点1","知识点2"]}]}]}，'
            "覆盖全部章节，重点章节细分更多知识点，总知识点数量控制在 20-40 个。"
        )
        if result and result.get("tree"):
            return result["tree"]

    # 降级：直接用文档解析出的章节标题构建两级知识树
    tree: list[dict] = []
    for title in outlines:
        if not title:
            continue
        if len(title) <= 30:
            tree.append({"chapter": title, "sections": [{"name": title, "points": [title]}]})
    if not tree:
        tree = [{"chapter": f"{course_name} 综合复习", "sections": [
            {"name": "通读全部资料", "points": ["课件通读", "错题回顾", "重点记忆"]}]}]
    return tree


def flatten_points(tree: list[dict]) -> list[dict]:
    """知识树展平为 [{chapter, section, point}]。"""
    flat = []
    for ch in tree:
        for sec in ch.get("sections", []):
            for pt in sec.get("points", []):
                flat.append({"chapter": ch.get("chapter", ""), "section": sec.get("name", ""), "point": pt})
    return flat


def schedule_plan(flat: list[dict], exam_date: datetime, start: datetime | None = None,
                  hours_per_day: float = 2.0) -> list[list[dict]]:
    """把知识点分配到每一天。最后一天留作整体回顾，考前一天半负载。"""
    start = start or datetime.now()
    total_days = max((exam_date.date() - start.date()).days, 1)
    study_days = total_days if total_days == 1 else total_days - 1  # 考前最后一天轻量回顾
    points = list(flat)
    if not points:
        return []
    per_day = -(-len(points) // max(study_days, 1))
    days: list[list[dict]] = []
    idx = 0
    for d in range(study_days):
        day_points = points[idx: idx + per_day]
        idx += per_day
        if not day_points and days:
            break
        days.append(day_points)
    while idx < len(points):  # 兜底：剩余塞进最后一天
        days[-1].extend(points[idx:])
        idx += per_day
    # 考前一天：整体回顾提示
    if total_days > 1:
        days.append([{"chapter": "考前回顾", "section": "查漏补缺",
                      "point": "错题与薄弱知识点回顾、公式速记卡自测"}])
    return days


async def create_plan(db: Session, user_id: int, course_id: int, course_name: str,
                      exam_date: datetime, hours_per_day: float = 2.0) -> Exam:
    tree = await build_knowledge_tree(db, user_id, course_id, course_name)
    flat = flatten_points(tree)
    days = schedule_plan(flat, exam_date, hours_per_day=hours_per_day)

    exam = Exam(user_id=user_id, course_id=course_id, course_name=course_name,
                exam_date=exam_date,
                knowledge_tree=json.dumps(tree, ensure_ascii=False))
    db.add(exam)
    db.flush()
    start = datetime.now()
    for i, day_points in enumerate(days):
        task = ReviewTask(
            user_id=user_id, exam_id=exam.id,
            day=start + timedelta(days=i),
            topics=json.dumps(day_points, ensure_ascii=False),
            order_index=i,
        )
        db.add(task)
    db.commit()
    return exam


def reschedule_after_progress(db: Session, exam: Exam) -> int:
    """某天任务完成后，把未完成且超期的知识点向后续日期匀载（简单重排）。"""
    tasks = db.query(ReviewTask).filter_by(exam_id=exam.id).order_by(ReviewTask.order_index).all()
    now = datetime.now()
    overdue_pending = []
    changed = 0
    for t in tasks:
        if t.day < now and not t.done:
            overdue_pending.extend(t.topics_list())
            t.topics = json.dumps([], ensure_ascii=False)
            changed += 1
    if not overdue_pending:
        return 0
    future = [t for t in tasks if t.day >= now and not t.done]
    if future:
        per = -(-len(overdue_pending) // len(future))
        for i in range(0, len(overdue_pending), per):
            j = i // per
            if j < len(future):
                future[j].topics = json.dumps(future[j].topics_list() + overdue_pending[i:i + per], ensure_ascii=False)
    elif tasks:
        tasks[-1].topics = json.dumps(tasks[-1].topics_list() + overdue_pending, ensure_ascii=False)
    db.commit()
    return changed


def plan_progress(exam: Exam, tasks: list[ReviewTask]) -> dict:
    total = sum(len(t.topics_list()) for t in tasks)
    done = sum(len(t.topics_list()) for t in tasks if t.done)
    return {
        "total_points": total,
        "done_points": done,
        "percent": round(done * 100 / total, 1) if total else 0.0,
        "total_days": len(tasks),
        "done_days": sum(1 for t in tasks if t.done),
    }
