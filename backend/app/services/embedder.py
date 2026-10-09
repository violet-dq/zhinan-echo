"""Embedding 服务：OpenAI 兼容 API（BGE-M3）优先，未配置时降级为本地 n-gram 哈希向量。

本地降级方案保证零 Key 演示可用；配置 SiliconFlow 的 BAAI/bge-m3 后即为报名表的技术路线。
"""
import hashlib
import logging
import math
import re
from collections import Counter

import httpx

from ..config import settings

logger = logging.getLogger("zhinan.embed")

_WORD = re.compile(r"[a-zA-Z0-9]+")
_LOCAL_DIM = 1024


def tokenize_for_local(text: str) -> list[str]:
    """中文按字符 bigram + unigram，英文按单词，用于本地哈希向量与 BM25。"""
    tokens: list[str] = []
    for word in _WORD.findall(text.lower()):
        tokens.append(word)
    cjk = re.findall(r"[\u4e00-\u9fff]", text)
    tokens.extend(cjk)
    tokens.extend(a + b for a, b in zip(cjk, cjk[1:]))
    return tokens


def _local_embed(text: str) -> list[float]:
    vec = [0.0] * _LOCAL_DIM
    tf = Counter(tokenize_for_local(text))
    for token, count in tf.items():
        h = int(hashlib.md5(token.encode()).hexdigest(), 16)
        idx = h % _LOCAL_DIM
        sign = 1.0 if ((h >> 64) & 1) == 0 else -1.0
        # 罕见词权重更高（近似 IDF）
        weight = 1.0 + math.log(1.0 + count)
        vec[idx] += sign * weight
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


class EmbeddingService:
    @property
    def enabled(self) -> bool:
        return settings.embedding_enabled

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """批量向量化；API 失败时降级本地方案，保证主流程不中断。"""
        if settings.embedding_enabled:
            result = await self._embed_api(texts)
            if result is not None:
                return result
            logger.warning("Embedding API 调用失败，降级为本地哈希向量")
        return [_local_embed(t) for t in texts]

    async def _embed_api(self, texts: list[str]) -> list[list[float]] | None:
        all_vecs: list[list[float]] = []
        batch = 16
        for i in range(0, len(texts), batch):
            part = texts[i:i + batch]
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.post(
                        f"{settings.embedding_api_base.rstrip('/')}/embeddings",
                        json={"model": settings.embedding_model, "input": part},
                        headers={"Authorization": f"Bearer {settings.embedding_api_key}"},
                    )
                    resp.raise_for_status()
                    data = sorted(resp.json()["data"], key=lambda d: d["index"])
                    all_vecs.extend(d["embedding"] for d in data)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Embedding API 批次失败: %s", exc)
                return None
        return all_vecs


embedder = EmbeddingService()
