"""FastAPI 应用入口：初始化网关 / 工具注册表 / Agent 注册表 / RAG 服务。

启动方式：
    cd backend && uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

from fastapi import FastAPI

from .agents.env_install_agent import EnvInstallAgent
from .agents.registry import AgentRegistry
from .api import routes_agents, routes_models, routes_rag, routes_system, routes_tools
from .config import get_settings
from .gateway.mock_model import MockModelBackend
from .gateway.openai_model import OpenAIModelBackend
from .gateway.router import ModelRouter
from .rag.service import KnowledgeService
from .tools.builtin import register_builtin_tools
from .tools.registry import ToolRegistry


def build_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.state.settings = settings

    # ---- 多模型网关：OpenAI 兼容端点 + Mock 兜底 ----
    backends = []
    for ep in settings.model_endpoints:
        if ep.enabled:
            backends.append(OpenAIModelBackend(settings, ep))
    backends.append(MockModelBackend("mock"))  # 始终注册 mock 作为最终降级
    app.state.model_router = ModelRouter(
        backends=backends,
        route_defaults=settings.route_defaults,
        mock_fallback_enabled=settings.mock_fallback_enabled,
    )

    # ---- 工具注册表 + 内置工具 ----
    app.state.tool_registry = ToolRegistry()
    register_builtin_tools(app.state.tool_registry, settings)

    # ---- Agent 注册表 + 环境安装 Agent Demo ----
    app.state.agent_registry = AgentRegistry()
    app.state.agent_registry.register(EnvInstallAgent(app.state.tool_registry))

    # ---- RAG 知识库（进程内简化实现）----
    app.state.knowledge = KnowledgeService(top_k=settings.rag_top_k)

    app.include_router(routes_system.router)
    app.include_router(routes_models.router, prefix="/api/v1")
    app.include_router(routes_tools.router, prefix="/api/v1")
    app.include_router(routes_agents.router, prefix="/api/v1")
    app.include_router(routes_rag.router, prefix="/api/v1")
    return app


app = build_app()
