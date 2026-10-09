"""SQLAlchemy 数据库会话管理（SQLite 开发模式 / PostgreSQL 生产模式）。"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

url = settings.database_url
# SQLite 并发优化：busy_timeout 等待锁而非立即失败；WAL 模式允许读写并发
connect_args = {"check_same_thread": False, "timeout": 30} if url.startswith("sqlite") else {}
engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True)

if url.startswith("sqlite"):
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models  # noqa: F401 确保模型注册
    os.makedirs(settings.data_dir, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    # 简易迁移：为已有表补列（SQLite ALTER TABLE ADD COLUMN）
    _migrate_add_columns()


def _migrate_add_columns() -> None:
    """对已有表补充新增列（仅添加，不删除/变更类型）。"""
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    if "users" not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns("users")}
    with engine.begin() as conn:
        if "avatar" not in existing:
            conn.execute(text("ALTER TABLE users ADD COLUMN avatar TEXT DEFAULT ''"))
        if "settings" not in existing:
            conn.execute(text("ALTER TABLE users ADD COLUMN settings TEXT DEFAULT '{}'"))
