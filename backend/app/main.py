"""知南·Echo 后端主入口。

lifespan 中完成：建表 → 种子数据 → 启动主动提醒后台循环。
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings
from .database import SessionLocal, init_db
from .routers import auth, chat, ddl, export, files, misc, review, user
from .services.reminders import reminder_loop
from .services.seed import seed_if_empty

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("zhinan.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_dirs()
    init_db()
    db = SessionLocal()
    try:
        await seed_if_empty(db, settings.data_dir)
    finally:
        db.close()
    reminder_task = asyncio.create_task(reminder_loop(SessionLocal))
    logger.info("知南·Echo 启动完成（LLM: %s, Embedding: %s）",
                "已启用" if settings.llm_enabled else "规则降级模式",
                "API" if settings.embedding_enabled else "本地哈希")
    yield
    reminder_task.cancel()


app = FastAPI(title=f"{settings.app_name} · {settings.app_desc}", lifespan=lifespan)


class NoCacheHtmlMiddleware(BaseHTTPMiddleware):
    """对 HTML 页面禁用缓存，确保浏览器始终获取最新 index.html（引用最新的 hashed CSS/JS）。"""
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        ct = response.headers.get("content-type", "")
        path = request.url.path
        logger.info(f"NoCacheMW: path={path} ct={ct} status={response.status_code}")
        # 对 HTML 响应（SPA 页面）禁用缓存；带 hash 的静态资源可正常缓存
        if "text/html" in ct or (not path.startswith("/api") and not path.startswith("/assets") and "." not in path.split("/")[-1]):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response


app.add_middleware(NoCacheHtmlMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (auth.router, chat.router, files.router, ddl.router,
               review.router, export.router, misc.router, user.router):
    app.include_router(router)


@app.get("/api/status")
def status():
    return {"app": settings.app_name, "status": "running",
            "llm": settings.llm_enabled, "embedding": settings.embedding_enabled}


@app.get("/api/health")
def health():
    return {"ok": True}


# 生产模式：若前端已构建（frontend/dist 存在）则由后端直接托管静态资源
# 兼容两种布局：服务器 /opt/echo/app + /opt/echo/frontend/dist；本地 backend/app + ../frontend/dist
_here = os.path.dirname(os.path.abspath(__file__))          # .../app
_parent = os.path.dirname(_here)                            # /opt/echo 或 .../backend
for _dist in (os.path.join(_parent, "frontend", "dist"),
              os.path.join(os.path.dirname(_parent), "frontend", "dist")):
    if os.path.isdir(_dist):
        app.mount("/", StaticFiles(directory=_dist, html=True), name="spa")
        break
