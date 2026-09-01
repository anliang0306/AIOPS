"""Agent 编排与环境安装 Agent：注册、生命周期、执行。"""
from __future__ import annotations

from app.agents.base import AgentStatus
from app.agents.env_install_agent import EnvInstallAgent
from app.agents.registry import AgentRegistry
from app.tools.builtin import register_builtin_tools
from app.tools.registry import ToolRegistry


def _setup(settings) -> tuple[AgentRegistry, str]:  # noqa: ANN001
    registry = AgentRegistry()
    tools = ToolRegistry()
    register_builtin_tools(tools, settings)
    registry.register(EnvInstallAgent(tools))
    return registry, "env-install-agent"


def test_agent_lifecycle(settings) -> None:  # noqa: ANN001
    registry, aid = _setup(settings)
    assert registry.get(aid).status == AgentStatus.REGISTERED
    registry.start(aid)
    assert registry.get(aid).status == AgentStatus.RUNNING
    registry.stop(aid)
    assert registry.get(aid).status == AgentStatus.STOPPED


def test_agent_requires_running(settings) -> None:  # noqa: ANN001
    registry, aid = _setup(settings)
    result = registry.run(aid, {"packages": ["git"]})
    assert result.ok is False
    assert "not running" in result.summary


def test_env_install_agent_run(settings) -> None:  # noqa: ANN001
    registry, aid = _setup(settings)
    registry.start(aid)
    result = registry.run(aid, {"packages": ["python", "git"]})
    assert result.ok is True
    assert len(result.details["checked"]) + len(result.details["to_install"]) == 2


def test_env_install_agent_missing_packages(settings) -> None:  # noqa: ANN001
    registry, aid = _setup(settings)
    registry.start(aid)
    result = registry.run(aid, {})
    assert result.ok is False
    assert "缺少 packages" in result.summary
