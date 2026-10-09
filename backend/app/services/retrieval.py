"""混合检索：向量召回 + BM25 召回 → RRF 融合重排（报名表 3.3 双路召回方案）。"""
import math
import re
from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from ..models import Chunk, DocumentFile
from .embedder import embedder, tokenize_for_local
from .vector_store import vector_store


@dataclass
class SearchHit:
    chunk_id: int
    file_id: int
    filename: str
    course_name: str
    section: str
    page: int
    text: str
    vector_score: float = 0.0
    bm25_score: float = 0.0
    rrf_score: float = 0.0


class BM25:
    """自实现 BM25（中文 bigram + 英文词），仅基于用户自己的 chunk。"""

    def __init__(self, corpus: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.docs = corpus
        self.doc_len = [len(d) for d in corpus]
        self.avgdl = (sum(self.doc_len) / len(corpus)) if corpus else 1.0
        self.df: Counter = Counter()
        for d in corpus:
            self.df.update(set(d))
        self.n = len(corpus)

    def idf(self, term: str) -> float:
        df = self.df.get(term, 0)
        return math.log((self.n - df + 0.5) / (df + 0.5) + 1.0)

    def score(self, query_tokens: list[str], index: int) -> float:
        doc = self.docs[index]
        tf = Counter(doc)
        total, dl = 0.0, self.doc_len[index] or 1
        for term in query_tokens:
            if term not in tf:
                continue
            idf = self.idf(term)
            freq = tf[term]
            total += idf * freq * (self.k1 + 1) / (freq + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
        return total


def _short_query_tokens(query: str) -> list[str]:
    return [t for t in tokenize_for_local(query) if not re.fullmatch(r"[\u4e00-\u9fff]", t) or len(t) > 1]


async def hybrid_search(
    db: Session,
    user_id: int,
    query: str,
    course_id: int | None = None,
    top_k: int = 6,
    vec_recall: int = 20,
    bm25_recall: int = 20,
    rrf_k: int = 60,
) -> list[SearchHit]:
    """向量 + BM25 双路召回，RRF 融合重排。"""
    chunks: list[Chunk] = db.query(Chunk).filter(Chunk.user_id == user_id).all()
    if not chunks:
        return []
    if course_id is not None:
        valid_ids = {f.id for f in db.query(DocumentFile.id).filter_by(user_id=user_id, course_id=course_id)}
        chunks = [c for c in chunks if c.file_id in valid_ids]
    # 过滤过短的 chunk：BM25 对短文档天然偏高，标题块信息量不足
    chunks = [c for c in chunks if len(c.text.strip()) >= 40]
    if not chunks:
        return []
    chunk_by_id = {c.id: c for c in chunks}

    # ---- 路1：向量召回 ----
    qvec = await embedder.embed([query])
    vec_hits = vector_store.search(user_id, qvec[0], top_k=vec_recall, course_id=course_id)

    # ---- 路2：BM25 召回 ----
    docs_tokens = []
    for c in chunks:
        if c.bm25_tokens:
            docs_tokens.append(c.bm25_tokens.split("\u0001"))
        else:
            docs_tokens.append(tokenize_for_local(c.text))
    bm25 = BM25(docs_tokens)
    q_tokens = _short_query_tokens(query)
    bm25_hits = sorted(
        ((bm25.score(q_tokens, i), chunks[i].id) for i in range(len(chunks))),
        key=lambda x: -x[0],
    )[:bm25_recall]

    # ---- RRF 融合 ----
    rrf: dict[int, float] = {}
    for rank, (cid, score) in enumerate(vec_hits):
        rrf[cid] = rrf.get(cid, 0.0) + 1.0 / (rrf_k + rank + 1)
        if cid in chunk_by_id and chunk_by_id[cid].id == cid:
            pass
    vec_score_map = {cid: s for cid, s in vec_hits}
    for rank, (score, cid) in enumerate(bm25_hits):
        rrf[cid] = rrf.get(cid, 0.0) + 1.0 / (rrf_k + rank + 1)

    file_ids = {c.file_id for c in chunks}
    files = db.query(DocumentFile).filter(DocumentFile.id.in_(file_ids)).all()
    file_map = {f.id: f for f in files}
    course_names = {}
    for f in files:
        course_names[f.id] = f.course.name if f.course else "未分类"

    hits: list[SearchHit] = []
    for cid, s in sorted(rrf.items(), key=lambda x: -x[1])[:top_k]:
        c = chunk_by_id.get(cid)
        if c is None:
            continue
        f = file_map.get(c.file_id)
        hits.append(SearchHit(
            chunk_id=cid, file_id=c.file_id,
            filename=f.filename if f else "未知文件",
            course_name=course_names.get(c.file_id, "未分类"),
            section=c.section or "", page=c.page or 1,
            text=c.text,
            vector_score=round(float(vec_score_map.get(cid, 0.0)), 4),
            bm25_score=0.0, rrf_score=round(s, 6),
        ))
    return hits


def hits_to_context(hits: list[SearchHit]) -> str:
    """把检索结果拼装成 LLM 上下文，带 [编号] 引用标记。"""
    parts = []
    for i, h in enumerate(hits, start=1):
        src = f"《{h.filename}》"
        if h.section:
            src += f" · {h.section}"
        if h.page:
            src += f" · 第{h.page}页"
        parts.append(f"[{i}] 来源：{src}\n{h.text}")
    return "\n\n".join(parts)
