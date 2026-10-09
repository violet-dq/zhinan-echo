"""主动提醒服务：截止前 7天/3天/1天/1小时 分档推送站内通知（可选邮件）。"""
import asyncio
import json
import logging
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText

from sqlalchemy.orm import Session

from ..config import settings
from ..models import DDL, Notification

logger = logging.getLogger("zhinan.reminder")

STAGES = [
    ("7d", timedelta(days=7), "warning", "一周后截止"),
    ("3d", timedelta(days=3), "warning", "3天后截止"),
    ("1d", timedelta(days=1), "urgent", "明天截止"),
    ("1h", timedelta(hours=1), "urgent", "1小时后截止"),
]


def _fmt(dt: datetime) -> str:
    return dt.strftime("%m月%d日 %H:%M")


def scan_and_notify(db: Session) -> int:
    """扫描所有 pending 且未过期的 DDL，按档位发通知。返回发送条数。"""
    now = datetime.now()
    sent = 0
    ddls = db.query(DDL).filter(DDL.status == "pending", DDL.due_at > now).all()
    for ddl in ddls:
        reminded = ddl.reminded_list()
        time_left = ddl.due_at - now
        for key, window, level, label in STAGES:
            if key in reminded:
                continue
            if time_left <= window:
                days = time_left.total_seconds() / 86400
                human = f"{int(days)}天" if days >= 1 else f"{int(time_left.total_seconds() // 3600)}小时"
                notif = Notification(
                    user_id=ddl.user_id, ddl_id=ddl.id, level=level,
                    title=f"⏰ {label}：{ddl.title}",
                    body=f"{ddl.title} 将于 {_fmt(ddl.due_at)} 截止（约{human}后），请尽快完成。",
                )
                db.add(notif)
                reminded.append(key)
                ddl.reminded = json.dumps(reminded)
                sent += 1
                if settings.email_enabled:
                    _send_email(db, ddl, label)
                break
    if sent:
        db.commit()
    return sent


def _send_email(db: Session, ddl: DDL, label: str) -> None:
    from ..models import User
    user = db.get(User, ddl.user_id)
    if not user or not user.email:
        return
    try:
        msg = MIMEText(f"【知南·Echo】提醒：{ddl.title} {label}（{_fmt(ddl.due_at)} 截止）。", "plain", "utf-8")
        msg["Subject"] = f"⏰ {label}：{ddl.title}"
        msg["From"] = settings.smtp_user
        msg["To"] = user.email
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10) as s:
            s.login(settings.smtp_user, settings.smtp_password)
            s.sendmail(settings.smtp_user, [user.email], msg.as_string())
    except Exception as exc:  # noqa: BLE001
        logger.warning("邮件提醒发送失败: %s", exc)


async def reminder_loop(session_factory, interval_sec: int = 60) -> None:
    """后台循环：每分钟扫描一次。"""
    logger.info("主动提醒服务已启动（每 %d 秒扫描）", interval_sec)
    while True:
        try:
            db = session_factory()
            try:
                scan_and_notify(db)
            finally:
                db.close()
        except Exception:  # noqa: BLE001
            logger.exception("提醒扫描异常")
        await asyncio.sleep(interval_sec)
