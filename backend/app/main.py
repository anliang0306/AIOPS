"""FastAPI 应用入口：初始化数据库 / 网关 / 工具 / Agent / ITSM / RAG / 自愈。

启动方式：
    cd backend && uvicorn app.main:app --reload --port 8000

Phase 2 新增：SQLite 数据持久化、ITSM 工单引擎、故障自愈 Agent（审批流）。
"""
from __future__ import annotations

from fastapi import FastAPI

from .agents.env_install_agent import EnvInstallAgent
from .agents.registry import AgentRegistry
from .api import (routes_agents, routes_autoheal, routes_itsm, routes_models,
                  routes_rag, routes_system, routes_tools)
from .autoheal.agent import AutohealAgent
from .config import get_settings
from .db.session import Database
from .gateway.mock_model import MockModelBackend
from .gateway.openai_model import OpenAIModelBackend
from .gateway.router import ModelRouter
from .itsm.service import ITSMService
from .rag.service import KnowledgeService
from .tools.builtin import register_builtin_tools
from .tools.registry import ToolRegistry


def build_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.state.settings = settings

    # ---- 数据持久化（Phase 2）----
    database = Database(settings.database_url)
    database.create_all()
    app.state.database = database

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

    # ---- RAG 知识库（进程内简化实现）----
    app.state.knowledge = KnowledgeService(top_k=settings.rag_top_k)

    # ---- ITSM 服务 + 故障自愈 Agent（Phase 2）----
    itsm = ITSMService(
        autoheal_high_risk_requires_approval=settings.autoheal_high_risk_requires_approval)
    app.state.itsm = itsm
    autoheal = AutohealAgent(
        itsm=itsm, tools=app.state.tool_registry, knowledge=app.state.knowledge,
        session_provider=database.new_session,
    )
    app.state.autoheal = autoheal

    # ---- Agent 注册表 + 环境安装 Agent / 故障自愈 Agent ----
    app.state.agent_registry = AgentRegistry()
    app.state.agent_registry.register(EnvInstallAgent(app.state.tool_registry))
    app.state.agent_registry.register(autoheal)

    app.include_router(routes_system.router)
    app.include_router(routes_models.router, prefix="/api/v1")
    app.include_router(routes_tools.router, prefix="/api/v1")
    app.include_router(routes_agents.router, prefix="/api/v1")
    app.include_router(routes_rag.router, prefix="/api/v1")
    app.include_router(routes_itsm.router, prefix="/api/v1")
    app.include_router(routes_autoheal.router, prefix="/api/v1")
    return app


app = build_app()

