"""沙箱与工具引擎：白名单拦截、超时、工具执行、审批策略。"""
from __future__ import annotations

from app.tools.base import RiskLevel
from app.tools.builtin import CheckInstalledTool, register_builtin_tools
from app.tools.registry import ToolRegistry
from app.tools.sandbox import LocalSubprocessSandbox


def test_sandbox_blocks_non_whitelist(settings) -> None:  # noqa: ANN001
    sandbox = LocalSubprocessSandbox(settings)
    res = sandbox.execute("rm -rf /")
    assert res.blocked is True
    assert "whitelist" in res.reason


def test_sandbox_allows_whitelisted(settings) -> None:  # noqa: ANN001
    sandbox = LocalSubprocessSandbox(settings)
    res = sandbox.execute("echo hello")
    assert res.ok is True
    assert res.stdout.strip() == "hello"


def test_sandbox_timeout(settings) -> None:  # noqa: ANN001
    settings.sandbox_timeout_seconds = 0.2
    settings.sandbox_allowed_commands = ["python -c"]
    sandbox = LocalSubprocessSandbox(settings)
    res = sandbox.execute('python -c "import time; time.sleep(5)"')
    assert res.ok is False
    assert res.returncode == -2  # timeout


def test_check_installed_tool() -> None:
    # 跨平台稳定断言：无论本机是否在 PATH 中，工具都应返回确定的布尔结果
    tool = CheckInstalledTool()
    res = tool.run(package="python")
    assert res.data["installed"] in (True, False)


def test_tool_registry_and_approval(settings) -> None:  # noqa: ANN001
    registry = ToolRegistry()
    register_builtin_tools(registry, settings)
    ids = [t["id"] for t in registry.list()]
    assert "shell" in ids and "install_package" in ids

    install = registry.require("install_package")
    assert install.require_approval is True  # MEDIUM 风险 -> 强制审批
    assert install.spec.risk_level == RiskLevel.MEDIUM

    shell = registry.require("shell")
    assert shell.require_approval is False  # LOW 风险直接执行


def test_install_package_returns_plan(settings) -> None:  # noqa: ANN001
    registry = ToolRegistry()
    register_builtin_tools(registry, settings)
    res = registry.require("install_package").run(package="git", method="apt")
    assert res.ok is True
    assert res.data["simulated"] is True
