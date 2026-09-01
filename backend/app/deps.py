"""应用依赖单例：从 app.state 获取全局组件。"""
from __future__ import annotations

from fastapi import Request

from .agents.registry import AgentRegistry
from .gateway.router import ModelRouter
from .rag.service import KnowledgeService
from .tools.registry import ToolRegistry


def get_model_router(request: Request) -> ModelRouter:
    return request.app.state.model_router


def get_tool_registry(request: Request) -> ToolRegistry:
    return request.app.state.tool_registry


def get_agent_registry(request: Request) -> AgentRegistry:
    return request.app.state.agent_registry


def get_knowledge(request: Request) -> KnowledgeService:
    return request.app.state.knowledge
