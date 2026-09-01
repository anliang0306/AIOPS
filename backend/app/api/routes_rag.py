"""知识库与 RAG API：文档入库、检索、上下文注入。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..deps import get_knowledge
from ..rag.service import KnowledgeService

router = APIRouter(prefix="/rag", tags=["rag"])


class AddDocumentRequest(BaseModel):
    doc_id: str
    text: str
    metadata: dict = {}


class SearchRequest(BaseModel):
    query: str
    top_k: int | None = None


@router.post("/documents")
def add_document(req: AddDocumentRequest,
                 kb: KnowledgeService = Depends(get_knowledge)) -> dict:
    chunk_ids = kb.add_document(req.doc_id, req.text, req.metadata)
    return {"doc_id": req.doc_id, "chunks": len(chunk_ids), "chunk_ids": chunk_ids}


@router.post("/search")
def search(req: SearchRequest, kb: KnowledgeService = Depends(get_knowledge)) -> dict:
    return {"hits": [h.model_dump() for h in kb.search(req.query, req.top_k)]}


@router.post("/context")
def build_context(req: SearchRequest,
                  kb: KnowledgeService = Depends(get_knowledge)) -> dict:
    return {"context": kb.build_context(req.query, req.top_k)}
