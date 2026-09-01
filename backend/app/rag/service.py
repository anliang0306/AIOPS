"""RAG 知识库服务（骨架阶段简化实现）。

- 使用进程内存储 + 字符 n-gram 相似度检索（不依赖 embedding 服务，可离线运行）；
- 预留 vector_store 配置字段（chromadb / milvus），Phase 2 起替换为真实向量库；
- 检索结果按 Top-K 返回，供 Agent / 客服注入上下文。
"""
from __future__ import annotations

import re
import threading
from collections import Counter

from pydantic import BaseModel


class KnowledgeChunk(BaseModel):
    chunk_id: str
    doc_id: str
    text: str
    metadata: dict = {}


class RagHit(BaseModel):
    chunk_id: str
    doc_id: str
    text: str
    score: float


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _ngrams(text: str, n: int = 2) -> Counter:
    t = _normalize(text)
    return Counter(t[i : i + n] for i in range(max(0, len(t) - n + 1)))


def _similarity(a: str, b: str) -> float:
    """Jaccard 式 n-gram 重叠度，范围 [0,1]；任一为空返回 0。"""
    ca, cb = _ngrams(a), _ngrams(b)
    if not ca or not cb:
        return 0.0
    inter = sum((ca & cb).values())
    union = sum((ca | cb).values())
    return inter / union if union else 0.0


class KnowledgeService:
    def __init__(self, top_k: int = 3) -> None:
        self._chunks: dict[str, KnowledgeChunk] = {}
        self._lock = threading.Lock()
        self._top_k = top_k

    def add_document(self, doc_id: str, text: str, metadata: dict | None = None,
                     chunk_size: int = 512) -> list[str]:
        """将文档按固定长度分块入库，返回 chunk_id 列表。"""
        chunk_ids: list[str] = []
        meta = dict(metadata or {})
        blocks = [text[i : i + chunk_size] for i in range(0, max(1, len(text)), chunk_size)]
        with self._lock:
            for idx, block in enumerate(blocks):
                cid = f"{doc_id}#{idx}"
                self._chunks[cid] = KnowledgeChunk(
                    chunk_id=cid, doc_id=doc_id, text=block, metadata=meta)
                chunk_ids.append(cid)
        return chunk_ids

    def search(self, query: str, top_k: int | None = None) -> list[RagHit]:
        k = top_k or self._top_k
        with self._lock:
            scored = [(c, _similarity(query, c.text)) for c in self._chunks.values()]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [
            RagHit(chunk_id=c.chunk_id, doc_id=c.doc_id, text=c.text, score=round(s, 4))
            for c, s in scored[:k] if s > 0
        ]

    def build_context(self, query: str, top_k: int | None = None) -> str:
        """把检索结果拼成可注入提示词的上下文。"""
        hits = self.search(query, top_k)
        if not hits:
            return ""
        parts = [f"[知识库 {i + 1}] {h.text}" for i, h in enumerate(hits)]
        return "\n\n".join(parts)

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._chunks)
