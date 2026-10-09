"""LangChain 工具定义层：用 @tool 装饰器把现有 handler 包装成可被 LLM function calling 调用的工具。

设计要点：
- 工具函数的 docstring 是 LLM 决定"何时调用此工具"的唯一依据，必须写清触发场景与参数含义
- db / user 上下文通过 build_tools(db, user) 工厂闭包注入，保持 @tool 函数签名纯净
- 工具返回统一的 {"reply": str, "cards": [...]} 结构，由 ToolNode 自动包装为 ToolMessage 回传给 LLM
- 复用 agent/tools.py 现有 handler，不重写业务逻辑
"""
import base64
import logging
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from langchain_core.tools import tool
from sqlalchemy.orm import Session

from ..config import settings
from ..models import DocumentFile, Exam, ReviewTask, User
from . import tools
from ..services.ingest import ingest_file
from ..services.parser import SUPPORTED_EXT

logger = logging.getLogger("zhinan.agent.tools_def")


def build_tools(db: Session, user: User) -> list:
    """每次请求动态构建工具列表，闭包捕获 db / user 上下文。

    返回的 list[BaseTool] 直接传给 ChatOpenAI.bind_tools() 与 langgraph.ToolNode。
    """

    @tool
    async def add_ddl(title: str, due_at: str, course: str = "", priority: str = "medium") -> dict:
        """当用户想记录、添加、登记、新建截止任务/作业/考试/DDL/截止日期时调用此工具。
        适用场景举例：用户说"算法第3章作业 8月20号晚上10点 截止"、"帮我记一下周五要交大物实验报告"、"下周三考离散"。
        参数：
        - title: 简洁的任务名（如"算法第3章作业"），从用户话中提炼，不要照搬整句
        - due_at: 截止时间，格式 YYYY-MM-DD HH:MM（24小时制），若无具体时间用 23:59
        - course: 课程名，必须来自用户的课程列表，未提及则留空
        - priority: 优先级 high(考试/答辩)/medium(作业/实验)/low，默认 medium
        """
        entities = {"title": title, "due_at": due_at, "course": course, "priority": priority}
        return await tools.handle_ddl_add(db, user, f"{title} {due_at}", entities)

    @tool
    def query_ddls(time_range: str = "", course: str = "") -> dict:
        """当用户想查询、列出、查看待办/截止任务/DDL清单时调用此工具。
        适用场景举例：用户说"今天有什么要交的"、"下周有哪些截止"、"本周待办"、"最近要交什么"。
        参数：
        - time_range: 时间范围关键词，从用户话中提取：今天/明天/后天/本周/这周/下周/周末/这学期，留空表示查全部
        - course: 课程名，若用户限定了某门课则填，否则留空
        """
        msg = f"{time_range} {course}".strip()
        return tools.handle_ddl_query(db, user, msg)

    @tool
    def complete_ddl(task_keyword: str = "") -> dict:
        """当用户表示某个任务/作业/DDL已经完成、做完、写完、交了、搞定了，想标记为已完成时调用此工具。
        适用场景举例：用户说"那个离散数学的小测验我做完了"、"算法作业交了"、"第一个任务完成了"。
        参数：
        - task_keyword: 用户提到的任务关键词（如"离散数学"、"算法作业"），用于匹配待办列表里的任务；留空则匹配最近的待办
        """
        return tools.handle_ddl_done(db, user, task_keyword or "完成了")

    @tool
    async def search_materials(query: str, course: str = "") -> dict:
        """当用户想检索、查找、搜索学习资料里的知识点、概念、问题答案时调用此工具（RAG 检索问答）。
        适用场景举例：用户说"二叉树有哪些遍历方式"、"讲一下进程同步"、"什么是抖动"、"频繁换页怎么处理"。
        参数：
        - query: 用户要检索的学习问题，用原话或提炼后的术语均可
        - course: 限定在某门课的资料里检索时填课程名，否则留空查全部资料
        """
        entities = {"course": course} if course else {}
        return await tools.handle_rag(db, user, query, entities)

    @tool
    def list_files(course: str = "") -> dict:
        """当用户想查看、列出资料库里有哪些文件/课件/文档/资料，或问有多少份资料时调用此工具。
        适用场景举例：用户说"我有哪些资料"、"资料库里有什么"、"数据结构有几份课件"、"看看我的文件"。
        参数：
        - course: 若用户限定某门课则填课程名，否则留空查全部资料库
        """
        if course:
            return tools.handle_file_organize(db, user, course)
        return tools.handle_file_query(db, user)

    @tool
    async def create_review_plan(course: str, exam_date: str) -> dict:
        """当用户想制定、生成、安排复习计划/备考计划时调用此工具。
        适用场景举例：用户说"我10月15号考数据结构 帮我安排复习"、"生成离散数学的备考计划"、"下个月要考算法 安排一下"。
        参数：
        - course: 课程名，必须来自用户的课程列表
        - exam_date: 考试日期，格式 YYYY-MM-DD
        """
        entities = {"course": course, "due_at": exam_date}
        return await tools.handle_review_plan(db, user, f"{course} {exam_date} 考试", entities)

    @tool
    def query_review_progress() -> dict:
        """当用户想查看复习进度、今天复习什么、复习到哪了、今日复习任务时调用此工具。
        适用场景举例：用户说"今天复习什么"、"复习进度怎么样"、"今天该学什么"、"复习计划到哪了"。
        """
        return tools.handle_review_query(db, user)

    @tool
    def toggle_review_task_reschedule(course: str = "", date: str = "今天", done: bool = True) -> dict:
        """当用户表示完成了某天的复习任务、想勾掉复习计划里的某项、标记今日复习已完成时调用此工具。调用后会自动把后续未完成的超期任务重新匀载到未来日期（智能重排）。
        适用场景举例：用户说"今天的复习做完了"、"数据结构昨天的复习完成了"、"勾掉今天的复习任务"、"今日任务搞定了"。
        参数：
        - course: 课程名，用于匹配复习计划；留空则匹配最近的复习计划
        - date: 日期关键词，支持"今天"/"昨天"/"YYYY-MM-DD"；留空默认今天
        - done: True 表示标记完成（打勾），False 表示取消完成
        """
        from datetime import datetime as _dt, timedelta as _td
        now = _dt.now()
        if date in ("", "今天", "today"):
            target_date = now.date()
        elif date in ("昨天", "yesterday"):
            target_date = (now - _td(days=1)).date()
        else:
            try:
                target_date = _dt.strptime(date[:10], "%Y-%m-%d").date()
            except ValueError:
                target_date = now.date()
        # 找到对应的考试/复习计划
        exams_q = db.query(Exam).filter(Exam.user_id == user.id)
        if course:
            exams_q = exams_q.filter(Exam.course_name.contains(course))
        exam = exams_q.order_by(Exam.exam_date).first()
        if not exam:
            return {"reply": "没有找到对应的复习计划 🤔 先告诉我「我 X月X号考 XX课，帮我生成复习计划」即可开始。",
                    "cards": []}
        # 找到目标日期的复习任务
        day_start = _dt(target_date.year, target_date.month, target_date.day)
        day_end = day_start + _td(days=1)
        task = db.query(ReviewTask).filter(
            ReviewTask.exam_id == exam.id,
            ReviewTask.day >= day_start,
            ReviewTask.day < day_end,
        ).first()
        if not task:
            # 回退：找最近的未完成任务
            task = db.query(ReviewTask).filter(
                ReviewTask.exam_id == exam.id,
                ReviewTask.day <= now,
            ).order_by(ReviewTask.day.desc()).first()
        if not task:
            return {"reply": f"「{exam.course_name}」的复习计划里没有找到对应日期的任务 🤔",
                    "cards": []}
        return tools.mark_review_task(db, user, task.id, done)

    @tool
    def export_data(format: str = "") -> dict:
        """当用户想导出、下载、同步 DDL/复习计划/资料目录到日历、CSV、Markdown 时调用此工具。
        适用场景举例：用户说"把DDL导出到手机日历"、"下载复习清单"、"导出资料目录"、"同步到日历"。
        参数：
        - format: 导出格式提示（ics/csv/markdown），用户未指定则留空
        """
        return tools.handle_export()

    @tool
    def upload_file_guide(course: str = "") -> dict:
        """当用户想上传、导入、添加资料/文件/课件/文档，但没有提供具体文件路径或文件内容时调用此工具，返回上传引导卡片。
        适用场景举例：用户说"我想上传课件"、"怎么传资料"、"我要导入文件"、"加一份笔记"。
        参数：
        - course: 若用户提到要传某门课的资料则填课程名，否则留空
        """
        # 返回结构化的 upload_guide 卡片：前端会渲染一个内嵌的上传组件（直接选择文件 → 入库）
        existing = (db.query(DocumentFile).filter_by(user_id=user.id)
                    .order_by(DocumentFile.created_at.desc()).limit(3).all())
        return {
            "reply": "我来帮你上传课件 🌸 点击下面的「选择文件」按钮，或直接把文件拖进去就行——"
                     "我会自动解析全文、打标签（课程/类型/章节/关键词）、建立语义索引，"
                     "完成后这份资料就会出现在「资料库」里，你可以随时预览、下载或问我内容～",
            "cards": [{
                "type": "upload_guide",
                "data": {
                    "course": course or "",
                    "tip": "支持 PDF / Word / PPT / TXT / Markdown / 图片，单文件最大 "
                           f"{settings.max_upload_mb}MB",
                    "recent": [{"id": f.id, "filename": f.filename,
                                "course": f.course.name if f.course else "未分类"}
                               for f in existing],
                },
            }],
        }

    @tool
    async def upload_file_to_library(file_name: str, file_content_base64: str,
                                     course: str = "") -> dict:
        """当用户在对话里直接提供了文件内容（base64 编码）想入库到「资料库」时调用此工具。
        适用场景举例：用户粘贴了 base64 文本说"把这个文件加到资料库"，或上游 agent 把文件内容以 base64 形式传入。
        参数：
        - file_name: 文件名（含扩展名，如 "test.pdf"），扩展名必须属于支持范围
        - file_content_base64: 文件二进制内容的 base64 编码字符串（不要加 data:xxx;base64, 前缀，只放纯 base64）
        - course: 课程名，用于归类；留空则由系统自动从内容/文件名推断
        """
        name = (file_name or "").strip()
        if not name:
            return {"reply": "缺少文件名，无法入库。请告诉我文件名（含扩展名），例如 test.pdf。", "cards": []}
        ext = os.path.splitext(name)[1].lower()
        if ext not in SUPPORTED_EXT:
            return {"reply": f"暂不支持 {ext or '该'} 格式。支持 PDF/Word/PPT/TXT/Markdown/图片。", "cards": []}
        # 解码 base64 → 写入 uploads 目录 → 调用 ingest_file 入库
        try:
            raw = base64.b64decode(file_content_base64, validate=True)
        except Exception as exc:  # noqa: BLE001
            return {"reply": f"base64 解码失败：{exc} 请确认提供的是纯 base64 字符串。", "cards": []}
        if len(raw) > settings.max_upload_mb * 1024 * 1024:
            return {"reply": f"文件超过 {settings.max_upload_mb}MB 限制，无法入库。", "cards": []}
        uploads_dir = Path(settings.data_dir) / "uploads" / str(user.id)
        uploads_dir.mkdir(parents=True, exist_ok=True)
        dest = uploads_dir / f"{uuid.uuid4().hex}{ext}"
        try:
            with open(dest, "wb") as out:
                out.write(raw)
        except Exception as exc:  # noqa: BLE001
            logger.warning("写入上传文件失败: %s", exc)
            return {"reply": f"写入文件出错：{exc}", "cards": []}
        # 调用现有 ingest_file 入库（自动解析、分块、向量化、打标签）
        try:
            doc = await ingest_file(db, user.id, str(dest), name,
                                    forced_course_name=course or None)
            return {"reply": f"已入库 ✅《{name}》（{course or '自动识别课程'}），"
                             f"已解析全文并建立语义索引，现在可以在「资料库」预览/下载，"
                             f"也可以直接问我这份资料的内容啦 📚",
                    "cards": [{"type": "files", "data": {"items": [
                        {"id": doc.id, "filename": doc.filename,
                         "course": course or "自动识别", "chunks": doc.chunk_count}]}}]}
        except Exception as exc:  # noqa: BLE001
            logger.warning("入库失败 %s: %s", name, exc)
            return {"reply": f"入库时出错：{exc}", "cards": []}

    @tool
    async def ingest_file_by_path(file_path: str, course: str = "") -> dict:
        """当用户在对话里提供了本地文件的绝对路径，想让助手读取该路径并入库时调用此工具。
        适用场景举例：用户说"D:\\学习资料\\数据结构\\test.pdf 帮我导入"、"把 C:\\notes.md 加到资料库"、"导入这个文件 D:/a.docx"。
        参数：
        - file_path: 本地文件绝对路径（Windows 反斜杠或正斜杠均可），必须存在于服务器可访问的文件系统
        - course: 课程名，用于归类；留空则由系统自动从路径推断
        """
        path = Path(file_path.strip().strip('"').strip("'"))
        if not path.exists():
            return {"reply": f"找不到这个文件：{file_path} 请确认路径是否正确，或直接把文件拖进左侧「资料库」上传区～",
                    "cards": []}
        if path.suffix.lower() not in SUPPORTED_EXT:
            return {"reply": f"暂不支持 {path.suffix} 格式。支持的格式：PDF/Word/PPT/TXT/Markdown/图片。",
                    "cards": []}
        # 复制到 uploads 目录
        uploads_dir = Path(settings.data_dir) / "uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)
        dest = uploads_dir / f"user{user.id}_{path.name}"
        try:
            shutil.copy2(path, dest)
        except Exception as exc:  # noqa: BLE001
            logger.warning("复制文件失败 %s: %s", file_path, exc)
            return {"reply": f"读取文件出错：{exc} 可以直接把文件拖进左侧「资料库」上传区～", "cards": []}
        # 调用现有 ingest_file 入库（自动解析、分块、向量化、打标签）
        try:
            doc = await ingest_file(db, user.id, str(dest), path.name,
                                    forced_course_name=course or None)
            return {"reply": f"已入库 ✅《{path.name}》（{course or '自动识别课程'}），"
                             f"已解析全文并建立语义索引，现在可以直接问我这份资料的内容啦 📚",
                    "cards": [{"type": "files", "data": {"items": [
                        {"id": doc.id, "filename": doc.filename,
                         "course": course or "自动识别", "chunks": doc.chunk_count}]}}]}
        except Exception as exc:  # noqa: BLE001
            logger.warning("入库失败 %s: %s", file_path, exc)
            return {"reply": f"入库时出错：{exc} 可以直接把文件拖进左侧「资料库」上传区试试～", "cards": []}

    return [add_ddl, query_ddls, complete_ddl, search_materials, list_files,
            create_review_plan, query_review_progress, toggle_review_task_reschedule,
            export_data, upload_file_guide, upload_file_to_library, ingest_file_by_path]


# 系统提示词：指导 LLM 如何使用工具
TOOL_AGENT_SYSTEM_PROMPT = (
    "你是「知南·Echo」，一名懂学习、知节奏的大学生学业助手智能体。"
    "你能通过调用工具帮用户管理学习任务：记录DDL、查询待办、检索资料、制定复习计划、导入文件等。\n\n"
    "调用工具的规则：\n"
    "1. 根据用户发言判断意图，若匹配某个工具的场景就调用对应工具，用自然语言不要生硬\n"
    "2. 工具返回结果后，用简洁亲切的中文总结结果给用户，不要原样照搬工具返回的 JSON\n"
    "3. 若用户请求模糊（如想记DDL但没说截止时间），先调用工具尝试，工具会返回追问，把追问转述给用户\n"
    "4. 与学习管理无关的闲聊不要强行调用工具，直接友好回应即可\n"
    "5. 一次回复可以调用多个工具（如用户同时问DDL和资料）\n"
    "你说话亲切、简洁、有条理，善用简短的分点表达，不啰嗦。"
)
