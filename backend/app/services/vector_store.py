"""轻量本地向量库：按用户隔离的 JSON + 内存缓存 + 余弦检索。

比赛/演示阶段零外部依赖（报名表 4.3：Demo 阶段可使用本地存储+轻量向量库）；
生产可无缝替换为 Milvus/Qdrant（接口保持一致）。
"""
import json
import os
import threading
from dataclasses import dataclass

import numpy as np

from ..config import settings


@dataclass
class VectorItem:
    chunk_id: int
    file_id: int
    course_id: int | None
    dim: int


class LocalVectorStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._cache: dict[int, dict[str, dict]] = {}   # user_id -> {chunk_key: {"vec": np.array, ...}}
        os.makedirs(os.path.join(settings.data_dir, "vector_store"), exist_ok=True)

    def _path(self, user_id: int) -> str:
        return os.path.join(settings.data_dir, "vector_store", f"user_{user_id}.json")

    def _load(self, user_id: int) -> dict[str, dict]:
        if user_id in self._cache:
            return self._cache[user_id]
        path = self._path(user_id)
        data: dict[str, dict] = {}
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
            except json.JSONDecodeError:
                data = {}
        self._cache[user_id] = data
        return data

    def _save(self, user_id: int, data: dict[str, dict]) -> None:
        path = self._path(user_id)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, path)

    def add(self, user_id: int, items: list[dict]) -> None:
        """items: [{chunk_id, file_id, course_id, vector}]"""
        with self._lock:
            data = self._load(user_id)
            for it in items:
                data[str(it["chunk_id"])] = {
                    "chunk_id": it["chunk_id"],
                    "file_id": it["file_id"],
                    "course_id": it.get("course_id"),
                    "vec": list(it["vector"]),
                }
            self._save(user_id, data)

    def remove_file(self, user_id: int, file_id: int) -> None:
        with self._lock:
            data = self._load(user_id)
            changed = False
            for key in [k for k, v in data.items() if v.get("file_id") == file_id]:
                data.pop(key)
                changed = True
            if changed:
                self._save(user_id, data)

    def search(self, user_id: int, query_vec: list[float], top_k: int = 20,
               course_id: int | None = None, file_ids: list[int] | None = None) -> list[tuple[int, float]]:
        """余弦相似度检索，返回 [(chunk_id, score)]。"""
        with self._lock:
            data = self._load(user_id)
        if not data:
            return []
        q = np.asarray(query_vec, dtype=np.float32)
        qn = np.linalg.norm(q) or 1.0
        ids, vecs, scores = [], [], []
        for v in data.values():
            if course_id is not None and v.get("course_id") != course_id:
                continue
            if file_ids is not None and v.get("file_id") not in file_ids:
                continue
            vec = np.asarray(v["vec"], dtype=np.float32)
            denom = (np.linalg.norm(vec) or 1.0) * qn
            ids.append(v["chunk_id"])
            scores.append(float(np.dot(vec, q) / denom))
        if not ids:
            return []
        order = np.argsort(scores)[::-1][:top_k]
        return [(ids[i], scores[i]) for i in order]

    def count(self, user_id: int) -> int:
        return len(self._load(user_id))


vector_store = LocalVectorStore()
