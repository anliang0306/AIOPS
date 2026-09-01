"""多模型网关 API：模型列表、对话、任务路由、用量统计。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..deps import get_model_router
from ..gateway.base import ChatMessage
from ..gateway.router import ModelRouter
from ..gateway.usage import reset, snapshot

router = APIRouter(prefix="/models", tags=["models"])


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    task: str | None = None  # simple_qa / complex_reasoning / tool_call / code_gen / sensitive
    use_cache: bool = True
    temperature: float = 0.0


@router.get("")
def list_models(mr: ModelRouter = Depends(get_model_router)) -> dict:
    return snapshot(mr.backends)


@router.post("/chat")
def chat(req: ChatRequest, mr: ModelRouter = Depends(get_model_router)) -> dict:
    if not req.messages:
        raise HTTPException(status_code=400, detail="messages 不能为空")
    try:
        resp = mr.chat(
            req.messages, task=req.task,
            use_cache=req.use_cache, temperature=req.temperature,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return resp.model_dump()


@router.post("/usage/reset")
def usage_reset(mr: ModelRouter = Depends(get_model_router)) -> dict:
    reset(mr.backends)
    return {"ok": True}
