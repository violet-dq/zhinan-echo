"""中文自然语言日期时间解析（规则优先，LLM 兜底在 agent 层调用）。

支持格式示例：
    2026年8月16号 / 8月16日 / 8-16 / 8/16 / 8.16 / 0816号
    今天 / 明天 / 后天 / 大后天 / 本周日 / 下周三 / 下下周一天
    下午3点 / 晚上8点半 / 14:30 / 早上9点 / 凌晨2点 / 中午12点
    8月16号下午2点 / 明天晚上8点半 / 16号交
默认缺省时间为 23:59。
"""
import re
from datetime import datetime, timedelta

CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8,
          "九": 9, "十": 10, "十一": 11, "十二": 12, "两": 2, "廿": 20, "卅": 30}
CN_WEEK = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}


def _cn_to_int(s: str) -> int | None:
    s = s.strip()
    if s.isdigit():
        return int(s)
    if s in CN_NUM:
        return CN_NUM[s]
    # 十 / 十五 / 二十五
    if s.startswith("十"):
        rest = s[1:]
        return 10 + (CN_NUM.get(rest, 0) if rest else 0)
    if "十" in s:
        a, _, b = s.partition("十")
        return CN_NUM.get(a, 1) * 10 + (CN_NUM.get(b, 0) if b else 0)
    return None


def _resolve_date(text: str, now: datetime) -> tuple[datetime, str] | None:
    """返回 (日期datetime, 命中的原文)。只解析日期部分。"""
    m = re.search(r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*[号日]", text)
    if m:
        y, mo, d = map(int, m.groups())
        return datetime(y, mo, d), m.group(0)
    m = re.search(r"(\d{1,2})\s*月\s*(\d{1,2})\s*[号日]", text)
    if m:
        mo, d = int(m.group(1)), int(m.group(2))
        year = now.year if (mo, d) >= (now.month, now.day) or mo != now.month else now.year
        # 已经过去的日期视为明年（如 12 月说 "3月1号"）
        try:
            cand = datetime(year, mo, d)
        except ValueError:
            return None
        if cand < now - timedelta(days=2):
            cand = datetime(year + 1, mo, d)
        return cand, m.group(0)
    m = re.search(r"(\d{1,2})\s*[号日](?![\d年])", text)
    if m:
        d = int(m.group(1))
        cand = datetime(now.year, now.month, d)
        if cand < now - timedelta(days=2):
            cand = cand.replace(month=(cand.month % 12) + 1) if cand.month < 12 else datetime(cand.year + 1, 1, d)
        return cand, m.group(0)

    m = re.search(r"(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})", text)
    if m:
        y, mo, d = map(int, m.groups())
        try:
            return datetime(y, mo, d), m.group(0)
        except ValueError:
            return None
    m = re.search(r"(?<![\d.])(\d{1,2})[-/.](\d{1,2})(?![\d.])", text)
    if m:
        mo, d = int(m.group(1)), int(m.group(2))
        try:
            cand = datetime(now.year, mo, d)
        except ValueError:
            return None
        if cand < now - timedelta(days=2):
            cand = datetime(now.year + 1, mo, d)
        return cand, m.group(0)

    if "大后天" in text:
        return now + timedelta(days=3), "大后天"
    if "后天" in text:
        return now + timedelta(days=2), "后天"
    if "明天" in text:
        return now + timedelta(days=1), "明天"
    if "今天" in text or "今晚" in text:
        return now, "今天"
    if "本周末" in text:
        return now + timedelta(days=(6 - now.weekday()) % 7 or 7), "本周末"

    m = re.search(r"(下下)?周?([一二三四五六日天])", text)
    if m and re.search(r"(下下?周|星期)", text):
        wd = CN_WEEK[m.group(2)]
        base = now
        if m.group(1):  # 下下周
            base = now + timedelta(days=7)
        days_ahead = (wd - now.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        if m.group(1) and days_ahead <= 7:
            days_ahead += 7
        return now + timedelta(days=days_ahead), m.group(0)
    m = re.search(r"星期([一二三四五六日天])", text)
    if m:
        wd = CN_WEEK[m.group(1)]
        days_ahead = (wd - now.weekday()) % 7 or 7
        return now + timedelta(days=days_ahead), m.group(0)
    if "月底" in text:
        if now.month == 12:
            return datetime(now.year + 1, 1, 1) - timedelta(days=1), "月底"
        return datetime(now.year, now.month + 1, 1) - timedelta(days=1), "月底"
    if "下个月" in text or "下月" in text:
        nm = now.month + 1 if now.month < 12 else 1
        y = now.year if now.month < 12 else now.year + 1
        return datetime(y, nm, 1), "下个月"
    return None


def _resolve_time(text: str) -> tuple[int, int] | None:
    """返回 (hour, minute)；未解析到时间返回 None（默认 23:59 由调用方处理）。"""
    m = re.search(r"(\d{1,2})\s*[:：点时]\s*(\d{1,2})\s*分?", text)
    if m and re.search(r"(点|:|：|时)", text):
        return min(int(m.group(1)), 23), min(int(m.group(2)), 59)
    m = re.search(r"(\d{1,2})\s*(?:点|:|：|时)\s*半", text)
    if m:
        return min(int(m.group(1)), 23), 30
    m = re.search(r"(\d{1,2})\s*(?:点|:|：|时)(?!\d)", text)
    if m:
        return min(int(m.group(1)), 23), 0
    if "中午" in text or "正午" in text:
        return 12, 0
    if "晚上" in text or "今晚" in text or "夜里" in text or "傍晚" in text:
        return 20, 0
    if "下午" in text:
        return 14, 0
    if "上午" in text or "早上" in text or "早晨" in text:
        return 9, 0
    return None


def parse_datetime(text: str, now: datetime | None = None) -> tuple[datetime, str, bool] | None:
    """解析文本中的日期时间。

    返回 (datetime, 命中原文, 是否解析到具体时间)；
    解析不到日期时返回 None。只有时间没有日期时按今天/明天推断。
    """
    now = now or datetime.now()
    time_hit = _resolve_time(text)
    if "下午" in text or "中午" in text or "晚上" in text or "傍晚" in text:
        th = _resolve_time(text)
        if th and th[0] < 12:  # 下午3点 -> 15点
            th = (th[0] + 12, th[1])
            time_hit = th
    if "晚上" in text or "夜里" in text or "凌晨" in text:
        th = _resolve_time(text)
        if th and th[0] < 12 and "凌晨" not in text:
            time_hit = (th[0] + 12, th[1])

    date_hit = _resolve_date(text, now)
    if date_hit is None:
        return None
    dt, matched = date_hit
    hour, minute = time_hit if time_hit else (23, 59)
    if time_hit is None and "今晚" in text:
        hour, minute = 23, 0
    result = dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return result, matched, time_hit is not None


def relative_days_phrase(due: datetime, now: datetime | None = None) -> str:
    """生成「3天后」「明天」「今天」等友好描述。"""
    now = now or datetime.now()
    days = (due.date() - now.date()).days
    if days < 0:
        return f"已过{abs(days)}天"
    if days == 0:
        return "今天"
    if days == 1:
        return "明天"
    if days == 2:
        return "后天"
    if days < 30:
        return f"{days}天后"
    return f"{days // 30}个月{days % 30}天后"
