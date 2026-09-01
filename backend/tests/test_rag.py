"""RAG 知识库：分块入库、Top-K 检索、上下文注入。"""
from __future__ import annotations

from app.rag.service import KnowledgeService


def test_add_and_search() -> None:
    kb = KnowledgeService(top_k=2)
    kb.add_document("doc1", "Nginx 502 错误通常由后端服务不可用导致，请检查 upstream", {"type": "troubleshoot"})
    kb.add_document("doc2", "磁盘空间不足时清理 /var/log 下的大日志文件", {"type": "troubleshoot"})
    hits = kb.search("Nginx 502 怎么处理", top_k=2)
    assert len(hits) >= 1
    assert hits[0].doc_id == "doc1"


def test_build_context_injection() -> None:
    kb = KnowledgeService(top_k=1)
    kb.add_document("d", "这是一段关于故障自愈的知识")
    ctx = kb.build_context("故障自愈知识")
    assert "知识库 1" in ctx


def test_chunking() -> None:
    kb = KnowledgeService(top_k=3)
    ids = kb.add_document("big", "x" * 1200, chunk_size=512)
    assert len(ids) == 3  # 1200 字 -> 3 块
