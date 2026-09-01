"""内置工具集：受控 shell、软件检查、模拟安装（供环境安装 Agent Demo 使用）。"""
from __future__ import annotations

import shutil

from ..config import Settings
from .base import BaseTool, RiskLevel, ToolParam, ToolResult, ToolSpec, json_out, parse_args
from .sandbox import LocalSubprocessSandbox, SandboxExecutor


class ShellTool(BaseTool):
    """在白名单内执行 shell 命令（沙箱内）。"""

    spec = ToolSpec(
        id="shell",
        name="shell",
        description="在白名单命令内执行 shell 命令（沙箱隔离、超时限制）",
        risk_level=RiskLevel.LOW,
        params=[ToolParam(name="command", description="要执行的命令，须命中白名单")],
    )

    def __init__(self, sandbox: SandboxExecutor) -> None:
        super().__init__()
        self._sandbox = sandbox

    def run(self, **kwargs: Any) -> ToolResult:  # noqa: ANN401
        args = parse_args(self.spec, **kwargs)
        res = self._sandbox.execute(args["command"])
        return ToolResult(
            ok=res.ok,
            tool_id=self.spec.id,
            output=res.stdout,
            error=res.stderr or (res.reason if res.blocked else ""),
            data=res.model_dump(),
        )


class CheckInstalledTool(BaseTool):
    """检查本机软件是否已安装（command -v / --version）。"""

    spec = ToolSpec(
        id="check_installed",
        name="check_installed",
        description="检查软件是否已安装，返回版本信息",
        risk_level=RiskLevel.LOW,
        params=[ToolParam(name="package", description="软件名，如 python / git / pip")],
    )

    def run(self, **kwargs: Any) -> ToolResult:  # noqa: ANN401
        args = parse_args(self.spec, **kwargs)
        pkg = args["package"]
        path = shutil.which(pkg)
        if path is None:
            return ToolResult(ok=False, tool_id=self.spec.id, output=json_out(
                {"package": pkg, "installed": False, "path": None}),
                data={"package": pkg, "installed": False, "path": None})
        return ToolResult(ok=True, tool_id=self.spec.id,
                          output=json_out({"package": pkg, "installed": True, "path": path}),
                          data={"package": pkg, "installed": True, "path": path})


class SimulatedInstallTool(BaseTool):
    """模拟安装：生成安装计划并记录，不真正改动系统（安全演示用）。

    生产环境请替换为真实包管理工具实现（apt/yum/pip），并走人工审批。
    """

    spec = ToolSpec(
        id="install_package",
        name="install_package",
        description="安装软件包（骨架阶段为模拟安装，生成安装计划）",
        risk_level=RiskLevel.MEDIUM,
        params=[ToolParam(name="package", description="要安装的软件名"),
                ToolParam(name="method", description="安装方式，如 apt/pip", required=False)],
    )

    def run(self, **kwargs: Any) -> ToolResult:  # noqa: ANN401
        args = parse_args(self.spec, **kwargs)
        pkg, method = args["package"], args.get("method", "auto")
        plan = {
            "package": pkg,
            "method": method,
            "simulated": True,
            "steps": [f"check {pkg}", f"install {pkg} via {method}", f"verify {pkg}"],
        }
        return ToolResult(ok=True, tool_id=self.spec.id, output=json_out(plan), data=plan)


def register_builtin_tools(registry, settings: Settings) -> None:  # noqa: ANN001
    sandbox = LocalSubprocessSandbox(settings)
    registry.register(ShellTool(sandbox))
    registry.register(CheckInstalledTool())
    registry.register(SimulatedInstallTool())
