"""资料入库管线：解析全文 → LLM/规则自动打标签 → 分块 → 向量化入库。"""
import json
import logging
import os
import re
import time

from sqlalchemy.orm import Session

from ..config import settings
from ..models import Chunk, Course, DocumentFile
from .embedder import embedder
from .llm import llm
from .parser import SUPPORTED_EXT, ParsedDoc, chunk_document, parse_file
from .vector_store import vector_store

logger = logging.getLogger("zhinan.ingest")

DOC_TYPE_HINTS = [
    ("课件", ("课件", "讲义", "lecture", "slide", "第.*讲", "PPT", "教材", "参考材料", "复习提纲")),
    ("试题", ("试题", "试卷", "考试", "习题", "作业", "exam", "quiz", "homework", "模拟", "样卷", "例题")),
    ("笔记", ("笔记", "note", "复习提纲", "总结", "攻略", "复习", "答案", "参考答案")),
    ("论文", ("论文", "paper", "journal", "conference", "arxiv")),
]

KNOWN_COURSES = [
    # 用户「学习资料」文件夹内的真实 12 门课程（目录名）
    "数据结构", "C++", "大学物理下", "大学物理", "数据库", "概率与统计", "概率论",
    "模拟电子线路", "模电", "电路", "离散数学", "算法设计与分析", "算法",
    "计算机导论", "计算机网络", "计网", "计算机逻辑基础", "逻辑基础", "数电",
    "面向对象编程", "面向对象", "OOP",
    # 原有公开课程名
    "操作系统", "计算机组成原理", "组成原理", "计组",
    "机器学习", "人工智能", "高等数学", "线性代数", "英语", "政治",
    "编译原理", "软件工程",
]

# 「学习资料」顶层目录名 → 标准课程名映射
FOLDER_COURSE_MAP = {
    "C++": "C++ 程序设计",
    "大学物理下": "大学物理（下）",
    "数据库": "数据库系统",
    "数据结构": "数据结构",
    "概率与统计": "概率论与数理统计",
    "模拟电子线路": "模拟电子线路（模电）",
    "电路": "电路分析",
    "离散数学": "离散数学",
    "算法设计与分析": "算法设计与分析",
    "计算机导论": "计算机导论",
    "计算机网络": "计算机网络",
    "计算机逻辑基础": "数字逻辑与计算机组成",
    "面向对象编程": "面向对象程序设计",
}


def guess_course_from_path(file_path: str) -> str | None:
    """从「学习资料/<课程名>/...」的第一层目录名识别课程，最可靠。"""
    norm = os.path.normpath(file_path)
    parts = norm.split(os.sep)
    # 找到"学习资料"后下一层
    try:
        idx = parts.index("学习资料")
    except ValueError:
        return None
    if idx + 1 >= len(parts):
        return None
    folder = parts[idx + 1]
    # 二级目录如果是"期末试卷/PPT/课件/习题/..."这种分类，再往下一层取
    generic = {"期末试卷", "PPT", "PPT与教材", "课件", "习题", "作业答案",
               "课件及参考材料", "课件及作业答案", "其他参考复习资料", "其他复习材料",
               "习题及答案", "习题和答案", "习题及答案",
               "实验", "复习", "复习参考材料", "复习重点",
               "PPT与教材", "教材", "题库", "作业答案（老师手写版）",
               "上机实验报告模板", "上机实验题目", "其他复习材料", "ppt(stk)", "ppt(tl)",
               "名词解释", "填空", "综合题", "试卷汇总",
               "练习题", "部分课后作业答案", "2009", "2014", "2016", "2017"}
    folder2 = ""
    if folder in generic and idx + 2 < len(parts):
        folder2 = parts[idx + 2]
    course_key = folder2 or folder
    return FOLDER_COURSE_MAP.get(course_key, course_key or None)


def guess_course_from_name(filename: str, content: str = "") -> str | None:
    for scope in (filename, content[:2000]):
        for course in KNOWN_COURSES:
            if course and course in scope:
                if course in ("组成原理", "计组"):
                    return "计算机组成原理"
                if course == "计网":
                    return "计算机网络"
                if course == "模电":
                    return "模拟电子线路（模电）"
                if course == "数电":
                    return "数字逻辑与计算机组成"
                if course == "算法":
                    return "算法设计与分析"
                if course == "概率论":
                    return "概率论与数理统计"
                if course == "面向对象" or course == "OOP":
                    return "面向对象程序设计"
                if course == "大学物理":
                    return "大学物理（下）"
                return FOLDER_COURSE_MAP.get(course, course)
    return None


def guess_doc_type(filename: str, content: str = "") -> str | None:
    text = filename + " " + content[:2000]
    for dtype, pats in DOC_TYPE_HINTS:
        for p in pats:
            if re.search(p, text, re.I):
                return dtype
    return "资料"


def extract_keywords(content: str, top_n: int = 8) -> list[str]:
    """规则关键词抽取（停用词过滤 + bigram 频次）。"""
    from .embedder import tokenize_for_local
    stop = set("的了和是在有对与及或我们把你们这个那个以及其中可以需要进行使用如下表示因此如果".split())
    tokens = [t for t in tokenize_for_local(content[:5000]) if t not in stop]
    from collections import Counter
    bigrams = [t for t in tokens if len(t) == 2]
    common = [w for w, _ in Counter(bigrams).most_common(top_n)]
    return common


async def auto_tags(filename: str, content: str, outline: list[dict], stored_path: str = "") -> dict:
    """LLM 自动标签（课程/类型/章节/关键词），无 LLM 时规则降级。标签为轻任务，用快速模型。"""
    # 1) 路径课程名（最高优先级，直接取「学习资料/<课程>」）
    course_from_path = guess_course_from_path(stored_path or filename) if stored_path else None

    if llm.enabled and content.strip():
        from ..config import settings
        hint = (
            "请为下面的学习资料生成归档标签。已知课程名请从这些里选最贴切的："
            "C++ 程序设计、大学物理（下）、数据库系统、数据结构、概率论与数理统计、"
            "模拟电子线路（模电）、电路分析、离散数学、算法设计与分析、计算机导论、"
            "计算机网络、数字逻辑与计算机组成、面向对象程序设计、"
            "操作系统、计算机组成原理、其他(自填)。\n"
        )
        if course_from_path:
            hint += f"（已知路径提示课程更可能是：{course_from_path}）\n"
        result = await llm.chat_json(
            hint +
            f"文件名：{filename}\n章节结构：{json.dumps([o.get('title') for o in outline[:15]], ensure_ascii=False)}\n"
            f"内容开头：{content[:1200]}\n"
            '输出 JSON：{"course":"课程名","type":"课件|试题|笔记|论文|资料","keywords":["关键词1","关键词2"],"sections":["章节1","章节2"]}',
            model=settings.llm_fast_model,
        )
        if result and result.get("course"):
            return {
                "course": result.get("course", "") or course_from_path or "",
                "type": result.get("type") or guess_doc_type(filename, content),
                "keywords": [str(k) for k in (result.get("keywords") or [])][:8],
                "sections": [str(s) for s in (result.get("sections") or [])][:12],
            }
    sections = [o.get("title", "") for o in outline[:12]]
    return {
        "course": course_from_path or guess_course_from_name(filename, content) or "",
        "type": guess_doc_type(filename, content),
        "keywords": extract_keywords(content),
        "sections": sections,
    }


def get_or_create_course(db: Session, user_id: int, name: str) -> Course | None:
    name = (name or "").strip()
    if not name:
        return None
    course = db.query(Course).filter_by(user_id=user_id, name=name).first()
    if course is None:
        course = Course(user_id=user_id, name=name)
        db.add(course)
        db.flush()
    return course


async def ingest_file(db: Session, user_id: int, stored_path: str, filename: str,
                      *,
                      forced_course_name: str | None = None,
                      forced_doc_type: str | None = None,
                      original_source_path: str | None = None) -> DocumentFile:
    """完整入库管线。抛出 ValueError 表示不可恢复的错误。

    参数（catalog 驱动场景）：
      - forced_course_name：catalog 给出的标准课程名（优先级最高，跳过 LLM/路径猜测）
      - forced_doc_type：catalog 已推断的资料类型（期末试卷/课件/…）
      - original_source_path：原始「学习资料/…」路径，用于 guess_course_from_path 回退（因为 stored_path 是 uploads 拷贝后的路径）
    """
    if os.path.getsize(stored_path) == 0:
        raise ValueError("文件内容为空，无法解析")
    try:
        parsed = parse_file(stored_path)
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("解析失败: %s", filename)
        raise ValueError(f"文档解析失败：{exc}") from exc

    # 选择最合适的「路径线索」让 guess_course_from_path 能命中「学习资料」
    effective_path = original_source_path or stored_path

    content = parsed.text.strip()
    if not content:
        # 极罕见情况下解析失败又兜底也为空：生成一条最小元数据占位，保证不整体跳过
        fallback_course = (forced_course_name
                           or guess_course_from_path(effective_path or filename)
                           or "未分类")
        content = (
            f"【未解析正文资料占位条目】文件名：{filename}\n"
            f"所属课程：{fallback_course}\n"
            f"资料类型：{forced_doc_type or '学习资料'}\n"
            f"说明：文件无法被自动抽取正文；此处仅记录文件名与所属课程信息，用于知识库条目留存和关键词命中。"
        )

    tags = await auto_tags(filename, content, parsed.outline, stored_path=effective_path)
    # 强制覆盖（来自 catalog 的确定性信息）
    if forced_course_name:
        tags["course"] = forced_course_name
    if forced_doc_type and tags.get("type") in (None, "", "资料"):
        tags["type"] = forced_doc_type
    course = get_or_create_course(db, user_id, tags.get("course") or "")

    # 最终修正：如果 parser 的占位内容写了"所属课程：未分类 / 资料分类：学习资料"等通用词，但我们手里有更强的确定信息（catalog force 参数），
    # 直接替换 content 里的对应行，确保向量库可检索到正确课程名。
    final_course = tags.get("course") or forced_course_name or "未分类"
    final_type = tags.get("type") or forced_doc_type or "学习资料"
    if "所属课程：未分类" in content and final_course != "未分类":
        content = content.replace("所属课程：未分类", f"所属课程：{final_course}")
    if "资料分类：学习资料" in content and final_type != "学习资料":
        content = content.replace("资料分类：学习资料", f"资料分类：{final_type}")
    # 同时把「资料类型：学习资料」行也覆盖
    if "资料类型：学习资料" in content and final_type != "学习资料":
        content = content.replace("资料类型：学习资料", f"资料类型：{final_type}")

    f = DocumentFile(
        user_id=user_id, course_id=course.id if course else None,
        filename=filename, file_type=os.path.splitext(filename)[1].lower().lstrip("."),
        size=os.path.getsize(stored_path), stored_path=stored_path,
        content=content, outline=json.dumps(parsed.outline, ensure_ascii=False),
        tags=json.dumps(tags, ensure_ascii=False), status="ready",
    )
    db.add(f)
    db.flush()

    # 如果 content 被修正过（course/type 被替换），需要用修正后文本重新分块 + 改写 ParsedDoc.pages 以免 chunk_document 仍读旧内容
    if final_course != "未分类" and "所属课程：未分类" in (parsed.text or ""):
        # 构造一份"修正文本"版本的 ParsedDoc 再切分
        fixed = ParsedDoc(
            text=content,
            outline=parsed.outline,
            pages={1: content},
            ocr_used=parsed.ocr_used,
        )
        chunks = chunk_document(fixed)
    else:
        chunks = chunk_document(parsed)

    chunk_rows, vec_items = [], []
    vectors = await embedder.embed([c["text"] for c in chunks]) if chunks else []
    for i, c in enumerate(chunks):
        from .embedder import tokenize_for_local
        row = Chunk(
            user_id=user_id, file_id=f.id, chunk_index=i, text=c["text"],
            page=c["page"], section=c["section"],
            bm25_tokens="\u0001".join(tokenize_for_local(c["text"])),
        )
        db.add(row)
        chunk_rows.append((row, vectors[i]))
    db.flush()
    for row, vec in chunk_rows:
        vec_items.append({
            "chunk_id": row.id, "file_id": f.id,
            "course_id": f.course_id, "vector": vec,
        })
    if vec_items:
        vector_store.add(user_id, vec_items)
    f.chunk_count = len(chunk_rows)
    db.commit()
    return f


async def reindex_file(db: Session, f: DocumentFile) -> None:
    """删除旧索引后重新入库（标签修改后同步向量库的 course_id）。"""
    db.query(Chunk).filter_by(file_id=f.id).delete()
    vector_store.remove_file(f.user_id, f.id)
    parsed = parse_file(f.stored_path)
    chunks = chunk_document(parsed)
    vectors = await embedder.embed([c["text"] for c in chunks]) if chunks else []
    from .embedder import tokenize_for_local
    vec_items = []
    for i, c in enumerate(chunks):
        row = Chunk(user_id=f.user_id, file_id=f.id, chunk_index=i, text=c["text"],
                    page=c["page"], section=c["section"],
                    bm25_tokens="\u0001".join(tokenize_for_local(c["text"])))
        db.add(row)
        db.flush()
        vec_items.append({"chunk_id": row.id, "file_id": f.id,
                          "course_id": f.course_id, "vector": vectors[i]})
    if vec_items:
        vector_store.add(f.user_id, vec_items)
    f.chunk_count = len(vec_items)
    db.commit()


def filename_ddl_hint(filename: str):
    """从文件名解析 DDL：返回 (标题, due_datetime) 或 (None, None)。

    支持模式（必须有"截止/前/交/due"类标记词，避免把版本号 2.1 误判为日期）：
        算法作业-0820截止.pdf / 高数作业 8月25号交.docx / 编译实验-9.1-due.pdf
    """
    import datetime as dt
    import re as _re
    now = dt.datetime.now()
    base = _re.sub(r"\.[a-zA-Z0-9]+$", "", filename)

    def _mk(mm: int, dd: int, title: str):
        try:
            due = dt.datetime(now.year, mm, dd, 23, 59)
        except ValueError:
            return None
        if due < now:
            try:
                due = dt.datetime(now.year + 1, mm, dd, 23, 59)
            except ValueError:
                return None
        cleaned = _re.sub(r"[-_—\s]*(截止|之前|前|due|交)", "", base, flags=_re.I)
        cleaned = _re.sub(r"[-_—\s]+(\d{4}|\d{1,2}[.\-_月]\d{1,2})[号日]?", "", cleaned)
        cleaned = cleaned.strip(" -_—")[:30]
        return (cleaned or base[:30]), due

    # MMDD：0820截止 / 0820前交
    m = _re.search(r"(?<!\d)(\d{4})\s*[号日]?\s*(截止|之前|前|due|交)", filename, _re.I)
    if m:
        r = _mk(int(m.group(1)[:2]), int(m.group(1)[2:]), base)
        if r:
            return r
    # 8月20号截止
    m = _re.search(r"(\d{1,2})\s*月\s*(\d{1,2})\s*[号日]?\s*(截止|之前|前|due|交)", filename)
    if m:
        r = _mk(int(m.group(1)), int(m.group(2)), base)
        if r:
            return r
    # 8.20截止 / 8-20-due / 8_20交
    m = _re.search(r"(\d{1,2})[.\-_](\d{1,2})\s*[-_—]?\s*(截止|之前|前|due|交)", filename, _re.I)
    if m:
        r = _mk(int(m.group(1)), int(m.group(2)), base)
        if r:
            return r
    return None, None


SUPPORTED = SUPPORTED_EXT
