"""导出中心：iCal(DDL→手机日历) / CSV+Markdown(资料目录) / Markdown(复习清单)。"""
import csv
import io
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from ..models import DDL, DocumentFile, Exam, ReviewTask


def _ics_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _ics_dt(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%S")


def export_ddl_ics(ddls: list[DDL]) -> str:
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0",
        "PRODID:-//ZhinanEcho//DDL Manager//CN", "CALSCALE:GREGORIAN",
    ]
    for i, d in enumerate(ddls, start=1):
        uid = f"zhinan-ddl-{d.id}@echo"
        end = d.due_at + timedelta(minutes=30)
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{_ics_dt(datetime.now())}",
            f"DTSTART;VALUE=DATE:{d.due_at.strftime('%Y%m%d')}",
            f"DTEND;VALUE=DATE:{(d.due_at + timedelta(days=1)).strftime('%Y%m%d')}",
            f"SUMMARY:{_ics_escape('⏰ ' + d.title)}",
            f"DESCRIPTION:{_ics_escape((d.detail or '')[:200])}",
            "BEGIN:VALARM", "TRIGGER:-P1D", "ACTION:DISPLAY",
            f"DESCRIPTION:{_ics_escape('明天截止：' + d.title)}", "END:VALARM",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


def export_files_csv(files: list[DocumentFile]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["文件名", "课程", "类型", "大小(KB)", "章节数", "关键词", "入库时间"])
    for f in files:
        tags = f.tags_dict()
        writer.writerow([
            f.filename,
            f.course.name if f.course else "未分类",
            tags.get("type", ""),
            round(f.size / 1024, 1),
            len(f.outline_list()),
            "、".join(tags.get("keywords", [])),
            f.created_at.strftime("%Y-%m-%d %H:%M") if f.created_at else "",
        ])
    return buf.getvalue()


def export_files_markdown(files: list[DocumentFile]) -> str:
    lines = ["# 📚 我的资料目录", "", f"> 导出时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}，共 {len(files)} 份资料", ""]
    by_course: dict[str, list] = {}
    for f in files:
        by_course.setdefault(f.course.name if f.course else "未分类", []).append(f)
    for course, fs in by_course.items():
        lines.append(f"## {course}")
        lines.append("")
        for f in fs:
            tags = f.tags_dict()
            lines.append(f"- **{f.filename}**（{tags.get('type', '资料')}，{round(f.size / 1024, 1)}KB）")
            if tags.get("sections"):
                lines.append(f"  - 章节：{'、'.join(tags['sections'][:8])}")
            if tags.get("keywords"):
                lines.append(f"  - 关键词：{'、'.join(tags['keywords'][:8])}")
        lines.append("")
    return "\n".join(lines)


def export_review_markdown(exam: Exam, tasks: list[ReviewTask]) -> str:
    lines = [
        f"# 📝 {exam.course_name} 复习计划",
        "",
        f"> 考试日期：{exam.exam_date.strftime('%Y-%m-%d')}　导出时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]
    total = sum(len(t.topics_list()) for t in tasks)
    done = sum(len(t.topics_list()) for t in tasks if t.done)
    lines.append(f"**进度：{done}/{total} 知识点（{round(done * 100 / total, 1) if total else 0}%）**")
    lines.append("")
    for t in sorted(tasks, key=lambda x: x.order_index):
        mark = "✅" if t.done else "⬜"
        lines.append(f"## {mark} {t.day.strftime('%m月%d日')}（第{t.order_index + 1}天）")
        for topic in t.topics_list():
            lines.append(f"- {topic.get('chapter', '')} · {topic.get('point', topic.get('section', ''))}")
        lines.append("")
    return "\n".join(lines)
