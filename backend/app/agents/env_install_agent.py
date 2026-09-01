"""环境安装 Agent Demo（Phase 1 单点 Agent）。

流程：依赖检查 -> 安装（骨架阶段为模拟安装）-> 验证。
所有操作通过 CLI 工具封装引擎（ToolRegistry）调用，体现"Agent 编排 + 工具封装"。
"""
from __future__ import annotations

from typing import Any

from ..tools.base import BaseTool
from ..tools.registry import ToolRegistry
from .base import AgentRunResult, BaseAgent


class EnvInstallAgent(BaseAgent):
    def __init__(self, tools: ToolRegistry) -> None:
        super().__init__(
            agent_id="env-install-agent",
            name="环境安装 Agent",
            description="自动完成环境依赖检查、安装与验证（Demo）",
            version="0.1.0",
        )
        self._tools = tools

    def _tool(self, tool_id: str) -> BaseTool:
        tool = self._tools.get(tool_id)
        if tool is None:
            raise KeyError(f"tool not found: {tool_id}")
        return tool

    def execute(self, payload: dict[str, Any]) -> AgentRunResult:  # noqa: ANN401
        packages: list[str] = payload.get("packages", []) or []
        if not packages:
            return AgentRunResult(agent_id=self.agent_id, ok=False, summary="缺少 packages 参数")

        report: dict[str, Any] = {"checked": [], "to_install": [], "installed": [], "failed": []}
        check = self._tool("check_installed")
        install = self._tool("install_package")

        for pkg in packages:
            res = check.run(package=pkg)
            if res.ok:
                report["checked"].append({"package": pkg, "status": "installed"})
                continue
            # 未安装 -> 生成安装计划（模拟）
            plan = install.run(package=pkg, method="auto")
            report["to_install"].append({"package": pkg, "plan": plan.data})
            # 模拟验证：骨架阶段假定模拟安装"成功"；真实实现需执行安装后复查
            verify = check.run(package=pkg)
            report["installed"].append({
                "package": pkg,
                "simulated": True,
                "verified": bool(verify.data.get("installed") if verify.ok else False),
            })

        ok = not report["failed"]
        summary = (
            f"检查 {len(report['checked'])} 个已安装，"
            f"生成 {len(report['to_install'])} 个安装计划（模拟），"
            f"失败 {len(report['failed'])}"
        )
        return AgentRunResult(agent_id=self.agent_id, ok=ok, summary=summary, details=report)
