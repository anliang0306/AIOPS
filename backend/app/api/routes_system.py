"""健康检查与系统信息。"""
from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(tags=["system"])


@router.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@router.get("/info")
def info(request: Request) -> dict:
    settings = request.app.state.settings
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "vector_store": settings.vector_store,
        "mock_fallback_enabled": settings.mock_fallback_enabled,
        "model_count": len(request.app.state.model_router.backends),
        "tool_count": len(request.app.state.tool_registry.list()),
        "agent_count": len(request.app.state.agent_registry.list()),
        "knowledge_chunks": request.app.state.knowledge.count,
    }
