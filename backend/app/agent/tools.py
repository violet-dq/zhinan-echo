"""智能体工具层：意图识别与各意图的处理逻辑（对话即操作的核心实现）。

所有 handler 返回 {"reply": str, "cards": [...]}，由 LangGraph 节点调用，
也可被 API 层直接复用（如文本批量提取 DDL）。
"""
import json
import re
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from ..models import Course, DDL, DocumentFile, Exam, ReviewTask, User
from ..services.dateparse import parse_datetime, relative_days_phrase
from ..services.llm import llm
from ..services.review import create_plan, plan_progress, reschedule_after_progress
from ..services.retrieval import hits_to_context, hybrid_search

INTENTS = ["ddl_add", "ddl_query", "ddl_done", "rag", "file_organize", "file_query",
           "review_plan", "review_query", "export", "smalltalk"]

HELP_TEXT = (
    "我是知南·Echo，你的学习管理智能体 🌸 这些事都可以直接对我说：\n"
    "· 记 DDL：「算法作业 8月20号 23:59 截止，帮我记一下」\n"
    "· 查 DDL：「下周有哪些截止任务？」「今天要交什么」\n"
    "· 查资料：「二叉树有哪些遍历方式？」「找一下进程管理的资料」\n"
    "· 传资料：在左侧「资料库」拖拽上传，我会自动解析、分类、打标签\n"
    "· 复习规划：「我 8 月 30 号考数据结构，帮我生成复习计划」「今天复习什么」\n"
    "· 导出：「把 DDL 导出到手机日历」——面板里也有一键导出中心"
)

RULE_KEYWORDS = [
    ("ddl_done", r"(完成了|做完了|写完了|交完了|搞定了).{0,12}(作业|ddl|DDL|任务)|(标记|勾掉|完成).{0,10}(ddl|DDL|任务|作业)"),
    ("ddl_query", r"(有(哪些|什么|多少)).{0,15}(ddl|DDL|截止|任务|要交|作业)|(ddl|DDL|任务|截止).{0,10}(有(哪些|什么)|列表|清单)|(今天|明天|后天|本周|这周|下周|周末|这学期).{0,12}(要?交|截止|ddl|DDL|任务)|要交什么|待办"),
    ("review_plan", r"(复习|备考).{0,15}(计划|规划|安排|怎么|表)|帮我(规划|安排).{0,10}复习|生成复习|考试.{0,8}(快到|准备)"),
    ("review_query", r"(今天|现在).{0,8}(复习|学)什么|复习(进度|到哪|得怎么样)|该复习"),
    ("export", r"导出|下载.{0,6}(日历|ics|日历文件)|同步到(手机)?日历"),
    ("file_query", r"(有(哪些|什么)).{0,10}(资料|文件|课件|文档)|资料(库|列表)|多少(份|个)(资料|文件)"),
    ("file_organize", r"(整理|归档|上传|导入|入库).{0,15}(资料|文件|课件|文档|文件夹)|批量.{0,6}(资料|文件)|(拖|传).{0,4}(文件|资料)"),
    ("ddl_add", r"(帮我|麻烦你?|记得|请)(一下)?(记|记一下|加|添加|录入|提醒)|(记|加|添)一个?(ddl|DDL|任务|作业|截止)|录入"),
    ("rag", r"(找|搜|检索|找一下|搜一下|查询|查一下).{0,24}|什么是|是什么|怎么(理解|做|实现)|(哪些|什么).{0,8}(方式|方法|类型|特点|区别|应用)|(是多少|哪几种|有几种|几种)"),
    # 兜底：较长的疑问句视为资料提问（DDL/复习等意图已在前面优先匹配）
    ("rag", r".{6,}[？?]$"),
]


# ---------------- 意图识别 ----------------

async def classify_intent(message: str, history: list[dict], courses: list[dict]) -> dict:
    """意图识别与槽位抽取：规则关键词优先（快且准），LLM 兜底泛化表达。返回 {intent, course, title, due_at, query}。"""
    entities: dict = {}
    for c in courses:
        if c["name"] in message:
            entities["course"] = c["name"]
            break
    # 1) 规则优先：命中即返回，无需调用 LLM
    for intent, pattern in RULE_KEYWORDS:
        if re.search(pattern, message):
            return {"intent": intent, **entities}
    # 2) LLM 兜底：处理规则未覆盖的表达
    if llm.enabled:
        course_names = [c["name"] for c in courses] or ["（暂无课程）"]
        recent = "\n".join(f"{m['role']}: {m['content'][:100]}" for m in history[-4:])
        result = await llm.chat_json(
            f"用户课程列表：{course_names}\n最近对话：\n{recent}\n用户当前发言：{message}\n\n"
            "请判断用户意图并抽取槽位，输出 JSON：\n"
            '{"intent":"ddl_add|ddl_query|ddl_done|rag|file_organize|file_query|review_plan|review_query|export|smalltalk",'
            '"course":"用户提到的课程名（必须来自课程列表，没提到则空串）",'
            '"title":"若录入DDL，给出简洁任务名（如：算法第3章作业）",'
            '"due_at":"若涉及截止/考试日期，输出 YYYY-MM-DD HH:MM（24小时制），没有则空串",'
            '"query":"若是资料检索，给出要检索的问题"}\n'
            "判定要点：用户想问学习资料里的知识点或概念时 intent=rag；"
            "想记录/添加截止任务时 intent=ddl_add；想查询已有任务时 intent=ddl_query；"
            "想制定复习安排时 intent=review_plan；想看复习进度或今日安排时 intent=review_query；"
            "与学习管理无关的闲聊 intent=smalltalk。"
        )
        if result and result.get("intent") in INTENTS:
            merged = {**entities, **{k: v for k, v in result.items() if v}}
            return merged
    return {"intent": "smalltalk", **entities}


# ---------------- DDL 处理 ----------------

def _match_course(db: Session, user: User, name: str) -> Course | None:
    if not name:
        return None
    return db.query(Course).filter(Course.user_id == user.id, Course.name.contains(name)).first()


def _guess_priority(title: str) -> str:
    if re.search(r"考试|答辩|面试|final|exam", title, re.I):
        return "high"
    if re.search(r"作业|homework|实验|lab|报告", title, re.I):
        return "medium"
    return "medium"


def _clean_title(message: str) -> str:
    """从口语中提取简洁任务名。"""
    t = re.sub(r"(帮我|麻烦你?|请|记得|记一下|一下|添加|录入|截止|之前|之前交|due)", "", message)
    t = re.sub(r"(\d{2,4}\s*[年]\s*)?\d{1,2}\s*[月./-]\s*\d{1,2}\s*[号日]?", "", t)
    t = re.sub(r"\d{1,2}\s*[:：点时]\s*\d{0,2}\s*分?半?", "", t)
    t = re.sub(r"(今天|明天|后天|下周|本周|这周|周[一二三四五六日天]|上午|下午|晚上|早上|中午|凌晨|傍晚|本?周末)+", "", t)
    t = re.sub(r"[，。,！!？?；;\s]+", " ", t).strip()
    return t.strip()[:30] or "学习任务"


async def extract_ddls_from_text(db: Session, user: User, text: str) -> list[DDL]:
    """从一段通知文字中批量提取 DDL（对话录入/文本批量提取共用）。

    先按句子切分做规则提取；无结果且有 LLM 时用模型兜底。
    """
    results: list[DDL] = []
    now = datetime.now()
    sentences = re.split(r"[；;\n]+|(?<=[。！？.])", text)
    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        hit = parse_datetime(sent, now)
        if hit is None:
            continue
        due, matched, has_time = hit
        title = sent.replace(matched, "").strip()
        title = re.sub(r"(各位同学|同学们|请注意|通知[:：]|请于?|之前|前|截止|due|至|到|另外|还有|提交|上交|安排在?)", "", title)
        title = re.sub(r"\d{1,2}\s*[:：]\s*\d{1,2}", "", title)
        title = re.sub(r"(上午|下午|晚上|早上|中午|凌晨)[\d\s]*点?", "", title)
        title = re.sub(r"[：:，。,！!？?\s]+", " ", title).strip()
        title = title[:40].strip()
        if len(title) < 2:
            title = _clean_title(sent)
        ddl = DDL(user_id=user.id, title=title or "学习任务", detail=sent[:500], due_at=due,
                  priority=_guess_priority(title), source="text")
        db.add(ddl)
        results.append(ddl)
    if not results and llm.enabled:
        ans = await llm.chat_json(
            f"今天是{now.strftime('%Y-%m-%d %A')}。请从下面的通知文字中提取全部截止任务：\n{text}\n"
            '输出 JSON：{"items":[{"title":"任务名","due_at":"YYYY-MM-DD HH:MM","detail":"补充说明"}]}，'
            "没有可提取的任务则输出 {\"items\":[]}。"
        )
        for it in (ans or {}).get("items", []):
            try:
                due = datetime.strptime((it.get("due_at") or "")[:16], "%Y-%m-%d %H:%M")
            except ValueError:
                continue
            ddl = DDL(user_id=user.id, title=str(it.get("title", "学习任务"))[:60],
                      detail=str(it.get("detail", ""))[:500], due_at=due,
                      priority=_guess_priority(str(it.get("title", ""))), source="text")
            db.add(ddl)
            results.append(ddl)
    db.commit()
    return results


async def handle_ddl_add(db: Session, user: User, message: str, entities: dict) -> dict:
    now = datetime.now()
    due = None
    if entities.get("due_at"):
        try:
            due = datetime.strptime(entities["due_at"][:16], "%Y-%m-%d %H:%M")
        except ValueError:
            due = None
    if due is None:
        hit = parse_datetime(message, now)
        if hit:
            due = hit[0]
    if due is None and llm.enabled:
        ans = await llm.chat_json(
            f"今天是{now.strftime('%Y-%m-%d %A')}。用户想记录一个截止任务：{message}\n"
            '输出 JSON：{"title":"简洁任务名","due_at":"YYYY-MM-DD HH:MM"}，'
            "若无法确定日期 due_at 输出空串。"
        )
        if ans and ans.get("due_at"):
            try:
                due = datetime.strptime(ans["due_at"][:16], "%Y-%m-%d %H:%M")
            except ValueError:
                due = None
    if due is None:
        return {"reply": "好的，我帮你记 ✍️ 不过我没听清截止时间——它是几月几号、几点截止呢？"
                         "（例如：8月20号晚上10点）", "cards": []}

    title = (entities.get("title") or "").strip() or _clean_title(message)
    course = _match_course(db, user, entities.get("course", "") or "")
    ddl = DDL(user_id=user.id, course_id=course.id if course else None, title=title,
              detail=message[:500], due_at=due, priority=_guess_priority(title), source="chat")
    db.add(ddl)
    db.commit()
    days_left = (due.date() - now.date()).days
    reply = (f"已记录 ✅「{title}」\n"
             f"截止：{due.strftime('%m月%d日 %H:%M')}（{relative_days_phrase(due, now)}）\n"
             f"我会在截止前 7 天 / 3 天 / 1 天 / 1 小时提醒你。")
    if course:
        reply = f"已记录 ✅「{title}」（{course.name}）\n截止：{due.strftime('%m月%d日 %H:%M')}（{relative_days_phrase(due, now)}）\n我会在截止前 7 天 / 3 天 / 1 天 / 1 小时提醒你。"
    return {"reply": reply, "cards": [{
        "type": "ddl_added",
        "data": {"id": ddl.id, "title": ddl.title, "due_at": due.isoformat(),
                 "days_left": days_left, "course": course.name if course else "",
                 "priority": ddl.priority},
    }]}


def _range_from_message(message: str) -> tuple[datetime | None, datetime | None]:
    m = message
    now = datetime.now()
    week_start = now - timedelta(days=now.weekday())
    if "今天" in m or "今日" in m:
        return now.replace(hour=0, minute=0), now.replace(hour=23, minute=59)
    if "明天" in m:
        t = now + timedelta(days=1)
        return t.replace(hour=0, minute=0), t.replace(hour=23, minute=59)
    if "后天" in m:
        t = now + timedelta(days=2)
        return t.replace(hour=0, minute=0), t.replace(hour=23, minute=59)
    if "下周" in m:
        nxt = week_start + timedelta(days=7)
        return nxt.replace(hour=0, minute=0), (nxt + timedelta(days=6)).replace(hour=23, minute=59)
    if "本周" in m or "这周" in m or "这学期" in m:
        return None, None  # 全部待办
    if "周末" in m:
        sat = week_start + timedelta(days=(5 - now.weekday()) % 7)
        return sat.replace(hour=0, minute=0), (sat + timedelta(days=1)).replace(hour=23, minute=59)
    return None, None


def query_ddls(db: Session, user: User, message: str = "") -> list[dict]:
    start, end = _range_from_message(message)
    q = db.query(DDL).filter(DDL.user_id == user.id, DDL.status == "pending")
    if start:
        q = q.filter(DDL.due_at >= start)
    if end:
        q = q.filter(DDL.due_at <= end)
    now = datetime.now()
    items = []
    for d in q.order_by(DDL.due_at).all():
        items.append({
            "id": d.id, "title": d.title, "due_at": d.due_at.isoformat(),
            "days_left": (d.due_at.date() - now.date()).days,
            "course": d.course.name if d.course else "", "priority": d.priority,
            "detail": d.detail[:120],
        })
    return items


def handle_ddl_query(db: Session, user: User, message: str) -> dict:
    items = query_ddls(db, user, message)
    if not items:
        scope = "近期"
        for w in ("今天", "明天", "本周", "这周", "下周", "周末"):
            if w in message:
                scope = w
                break
        return {"reply": f"{scope}没有待办的截止任务，很从容 🌿 需要我帮你规划复习或整理资料吗？",
                "cards": [{"type": "ddl_list", "data": {"items": []}}]}
    lines = [f"共 {len(items)} 项待办，按时间排序："]
    for it in items:
        course_tag = f"｜{it['course']}" if it["course"] else ""
        due = datetime.fromisoformat(it["due_at"])
        lines.append(f"· {it['title']}{course_tag}　⏰ {due.strftime('%m月%d日 %H:%M')}（{relative_days_phrase(due)}）")
    urgent = [i for i in items if i["days_left"] <= 1]
    if urgent:
        lines.append(f"\n⚠️ 其中 {len(urgent)} 项 24 小时内截止，建议优先处理！")
    lines.append("\n需要我为某门课生成复习计划吗？")
    return {"reply": "\n".join(lines), "cards": [{"type": "ddl_list", "data": {"items": items}}]}


def handle_ddl_done(db: Session, user: User, message: str) -> dict:
    pending = db.query(DDL).filter(DDL.user_id == user.id, DDL.status == "pending").order_by(DDL.due_at).all()
    if not pending:
        return {"reply": "目前没有待办任务，一切清零 🎉", "cards": []}
    target = None
    for d in pending:
        if d.title and any(k in message for k in [d.title[:4], d.title[-4:]] if len(k) >= 2):
            target = d
            break
    if target is None and len(pending) == 1:
        target = pending[0]
    if target is None:
        recent = pending[0]
        return {"reply": f"你完成了哪一项呀？最近的一项是「{recent.title}」（{recent.due_at.strftime('%m月%d日')} 截止），是它吗？",
                "cards": [{"type": "ddl_list", "data": {"items": query_ddls(db, user, "")}}]}
    target.status = "done"
    db.commit()
    return {"reply": f"太棒了 🎉「{target.title}」已完成！剩余 {db.query(DDL).filter_by(user_id=user.id, status='pending').count()} 项待办。",
            "cards": [{"type": "ddl_list", "data": {"items": query_ddls(db, user, "")}}]}


# ---------------- RAG 检索问答 ----------------

async def _expand_query(message: str) -> str:
    """LLM 查询改写：口语化提问 → 术语化关键词组合（弥补无语义向量时的同义词鸿沟）。

    用轻量快速模型执行，追求低延迟。
    """
    if not llm.enabled:
        return message
    from ..config import settings
    result = await llm.chat_json(
        "你是资料检索查询改写器。把用户的学习问题改写为检索关键词串，要求："
        "包含核心术语及其同义词/上位词/常见变体（如「频繁换页」→「抖动 颠簸 缺页 页面置换」），"
        "去掉口语虚词，共 5-15 个词，空格分隔，不要解释。\n"
        f"用户问题：{message}\n输出 JSON：{{\"query\":\"关键词1 关键词2 ...\"}}",
        model=settings.llm_fast_model,
    )
    return (result or {}).get("query", "").strip() or message


async def handle_rag(db: Session, user: User, message: str, entities: dict) -> dict:
    course = _match_course(db, user, entities.get("course", ""))
    search_query = await _expand_query(message)
    hits = await hybrid_search(db, user.id, search_query, course_id=course.id if course else None, top_k=5)
    scope = f"（范围：{course.name}）" if course else ""
    if not hits:
        total = db.query(DocumentFile).filter_by(user_id=user.id).count()
        if total == 0:
            return {"reply": f"你的资料库还是空的 {scope}——先把课件/笔记上传到「资料库」，我读完就能回答这类问题啦 📚",
                    "cards": []}
        return {"reply": f"在现有资料里没有检索到相关内容 {scope}。可以换个说法试试，或上传对应课程的资料后再来问我～",
                "cards": []}

    sources = []
    for i, h in enumerate(hits[:5], start=1):
        src = f"[{i}]《{h.filename}》"
        if h.section:
            src += f" · {h.section}"
        src += f" · 第{h.page}页"
        sources.append(src)

    if llm.enabled:
        answer = await llm.chat(
            [
                {"role": "system", "content":
                    "你是学习资料问答助手。仅依据下面的资料片段回答问题，回答末尾用 [编号] 标注引用来源（如 [1][2]）。"
                    "若资料不足以回答，请直说并建议查阅哪份资料。回答简洁、分点、面向备考，控制在 300 字内。"},
                {"role": "user", "content": f"资料片段：\n{hits_to_context(hits)}\n\n用户问题：{message}"},
            ],
            temperature=0.2, max_tokens=700,
        )
        if answer:
            return {"reply": f"{answer}\n\n📖 来源：\n" + "\n".join(sources),
                    "cards": [{"type": "sources", "data": {"sources": sources}}]}
    # 降级：直接返回最相关片段摘要
    top = hits[0]
    frag = top.text[:300] + ("…" if len(top.text) > 300 else "")
    return {"reply": f"为你找到最相关的内容{scope}：\n\n{frag}\n\n📄 完整内容见《{top.filename}》"
                     f"{(' · ' + top.section) if top.section else ''} · 第{top.page}页\n\n📖 全部来源：\n" + "\n".join(sources),
            "cards": [{"type": "sources", "data": {"sources": sources}}]}


# ---------------- 资料整理 ----------------

def handle_file_organize(db: Session, user: User, message: str) -> dict:
    course = None
    for c in db.query(Course).filter_by(user_id=user.id).all():
        if c.name in message:
            course = c
            break
    if course:
        files = db.query(DocumentFile).filter_by(user_id=user.id, course_id=course.id).all()
        return {"reply": f"「{course.name}」目前有 {len(files)} 份资料。把新的课件/试题拖进左侧「资料库」上传区，"
                         "我会自动解析全文、生成标签（课程/类型/章节/关键词）并归入对应课程目录；"
                         "上传完成后直接在这里问我任何知识点即可 📚",
                "cards": [{"type": "files", "data": {"items": [_file_card(f) for f in files[:10]]}}]}
    return {"reply": "没问题！把要整理的资料（PDF / Word / PPT / TXT / Markdown / 图片）拖进左侧「资料库」，"
                     "我会自动：① 解析全文与章节结构 ② 打上课程、类型（课件/试题/笔记/论文）、关键词标签 "
                     "③ 归入课程目录 ④ 建立语义索引，之后你随时用自然语言问我资料内容 🌸",
            "cards": []}


def _file_card(f: DocumentFile) -> dict:
    tags = f.tags_dict()
    return {"id": f.id, "filename": f.filename, "type": tags.get("type", ""),
            "course": f.course.name if f.course else "未分类",
            "keywords": tags.get("keywords", [])[:5], "sections": tags.get("sections", [])[:5],
            "size_kb": round(f.size / 1024, 1), "chunks": f.chunk_count}


def handle_file_query(db: Session, user: User) -> dict:
    files = db.query(DocumentFile).filter_by(user_id=user.id).order_by(DocumentFile.created_at.desc()).all()
    if not files:
        return {"reply": "资料库目前是空的，去左侧上传第一份资料吧 📂", "cards": []}
    by_course: dict[str, int] = {}
    for f in files:
        by_course[f.course.name if f.course else "未分类"] = by_course.get(f.course.name if f.course else "未分类", 0) + 1
    stat = "、".join(f"{k} {v}份" for k, v in by_course.items())
    return {"reply": f"资料库共 {len(files)} 份资料：{stat}。全部已建立语义索引，可以直接问我资料里的知识点～",
            "cards": [{"type": "files", "data": {"items": [_file_card(f) for f in files[:12]]}}]}


# ---------------- 复习规划 ----------------

async def handle_review_plan(db: Session, user: User, message: str, entities: dict) -> dict:
    now = datetime.now()
    exam_date = None
    if entities.get("due_at"):
        try:
            exam_date = datetime.strptime(entities["due_at"][:16], "%Y-%m-%d %H:%M")
        except ValueError:
            exam_date = None
    if exam_date is None:
        hit = parse_datetime(message, now)
        if hit:
            exam_date = hit[0]
    if exam_date is None and llm.enabled:
        ans = await llm.chat_json(
            f"今天是{now.strftime('%Y-%m-%d')}。用户想制定复习计划：{message}\n"
            '输出 JSON：{"course":"课程名（从用户话中提取）","exam_date":"YYYY-MM-DD"}，日期无法确定则空串。'
        )
        if ans and ans.get("exam_date"):
            try:
                exam_date = datetime.strptime(ans["exam_date"][:10], "%Y-%m-%d")
            except ValueError:
                exam_date = None
        if ans and ans.get("course") and not entities.get("course"):
            entities["course"] = ans["course"]

    course = _match_course(db, user, entities.get("course", ""))
    if course is None:
        courses = db.query(Course).filter_by(user_id=user.id).all()
        if not courses:
            return {"reply": "做复习计划前，先把这门课的资料传到「资料库」——我会根据资料里的章节结构提取知识树 🌱", "cards": []}
        names = "、".join(c.name for c in courses)
        return {"reply": f"好的，马上帮你规划 📝 是哪门课呢？（你目前的课程：{names}）", "cards": []}
    if exam_date is None:
        return {"reply": f"「{course.name}」收到！考试是几月几号呢？告诉我日期，我按剩余天数和知识点量帮你排期。", "cards": []}

    files_cnt = db.query(DocumentFile).filter_by(user_id=user.id, course_id=course.id).count()
    exam = await create_plan(db, user.id, course.id, course.name, exam_date)
    tasks = db.query(ReviewTask).filter_by(exam_id=exam.id).order_by(ReviewTask.order_index).all()
    prog = plan_progress(exam, tasks)
    days_card = [{
        "date": t.day.strftime("%m-%d"), "topics": t.topics_list(), "done": t.done,
    } for t in tasks]
    reply = (f"「{course.name}」复习计划已生成 ✅\n"
             f"· 考试：{exam_date.strftime('%m月%d日')}（{relative_days_phrase(exam_date)}）\n"
             f"· 依据：{files_cnt} 份资料提取的知识树，共 {prog['total_points']} 个知识点\n"
             f"· 安排：{prog['total_days']} 天，每天约 2 小时量，最后一天留作整体回顾\n"
             f"计划已同步到「复习计划」面板，完成后打勾，我会根据进度自动调整后续安排 🌸")
    return {"reply": reply, "cards": [{
        "type": "review_plan",
        "data": {"exam_id": exam.id, "course_name": course.name,
                 "exam_date": exam_date.strftime("%Y-%m-%d"), "progress": prog, "days": days_card},
    }]}


def handle_review_query(db: Session, user: User) -> dict:
    exams = db.query(Exam).filter_by(user_id=user.id).order_by(Exam.exam_date).all()
    now = datetime.now()
    exams = [e for e in exams if e.exam_date >= now - timedelta(days=1)]
    if not exams:
        return {"reply": "你还没有进行中的复习计划。告诉我「我 X月X号考 XX课，帮我生成复习计划」即可开始 🌱", "cards": []}
    replies, cards = [], []
    for exam in exams:
        tasks = db.query(ReviewTask).filter_by(exam_id=exam.id).order_by(ReviewTask.order_index).all()
        prog = plan_progress(exam, tasks)
        today_tasks = [t for t in tasks if t.day.date() == now.date()]
        cards.append({"type": "review_plan", "data": {
            "exam_id": exam.id, "course_name": exam.course_name,
            "exam_date": exam.exam_date.strftime("%Y-%m-%d"), "progress": prog,
            "days": [{"date": t.day.strftime("%m-%d"), "topics": t.topics_list(), "done": t.done} for t in tasks],
        }})
        if today_tasks:
            t = today_tasks[0]
            points = [p.get("point", "") for p in t.topics_list()][:6]
            replies.append(f"📅 今天（{exam.course_name}，{exam.exam_date.strftime('%m月%d日')} 考）：\n"
                           f"今日任务：{'、'.join(points)}\n进度：{prog['done_points']}/{prog['total_points']}"
                           f"（{prog['percent']}%）")
        else:
            replies.append(f"📅 {exam.course_name}：今天没有安排复习任务，进度 {prog['percent']}%。"
                           f"考试还有 {(exam.exam_date - now).days} 天。")
    return {"reply": "\n\n".join(replies), "cards": cards}


# ---------------- 导出 / 兜底 ----------------

def handle_export() -> dict:
    return {"reply": "导出中心在「DDL看板 → 导出」和「复习计划 → 导出」里：\n"
                     "· DDL → iCal 文件（可导入手机日历）\n"
                     "· 资料目录 → CSV / Markdown\n"
                     "· 复习清单 → Markdown\n"
                     "点击即可下载，数据带得走 ✨", "cards": []}


async def handle_smalltalk(db: Session, user: User, message: str, history: list[dict]) -> dict:
    if re.search(r"(你是谁|你会什么|帮助|怎么用|能做什么|功能)", message):
        return {"reply": HELP_TEXT, "cards": []}
    if llm.enabled:
        ctx = "\n".join(f"{m['role']}: {m['content'][:120]}" for m in history[-6:])
        answer = await llm.chat(
            [{"role": "user", "content":
                f"以下是用户与学业助手「知南·Echo」的对话：\n{ctx}\n用户：{message}\n"
                "请以知南·Echo 的身份简短回应；若与学习管理无关，友好回应一两句后把话题引回学习（DDL、资料整理、复习规划）。"}],
            temperature=0.6, max_tokens=300,
        )
        if answer:
            return {"reply": answer, "cards": []}
    return {"reply": "这个问题我还在学习中 🌱 我最擅长的是：记 DDL、查资料、做复习计划。要不要试试问我「下周有什么要交的」？\n" + HELP_TEXT,
            "cards": []}


def mark_review_task(db: Session, user: User, task_id: int, done: bool) -> dict:
    task = db.get(ReviewTask, task_id)
    if task is None or task.user_id != user.id:
        return {"reply": "任务不存在", "cards": []}
    task.done = done
    db.commit()
    exam = db.get(Exam, task.exam_id)
    reschedule_after_progress(db, exam)
    tasks = db.query(ReviewTask).filter_by(exam_id=exam.id).order_by(ReviewTask.order_index).all()
    prog = plan_progress(exam, tasks)
    return {"reply": f"已更新 ✅ 当前进度 {prog['done_points']}/{prog['total_points']}（{prog['percent']}%）",
            "cards": [{"type": "review_plan", "data": {
                "exam_id": exam.id, "course_name": exam.course_name,
                "exam_date": exam.exam_date.strftime("%Y-%m-%d"), "progress": prog,
                "days": [{"date": t.day.strftime("%m-%d"), "topics": t.topics_list(), "done": t.done} for t in tasks],
            }}]}


def to_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)
