"""沙箱执行环境。

骨架阶段实现：白名单命令 + 超时限制的本地受限子进程（LocalSubprocessSandbox），
用于演示与测试。生产环境必须切换为容器沙箱（DockerSandbox，见 docs/architecture.md）：
限制文件系统 / 网络 / CPU / 内存配额，高风险命令直接拦截。

平台说明：Windows 下命令经 cmd.exe 执行以支持内建命令（echo/type 等无独立 exe 的
命令），POSIX 平台保持 shlex 分词直执行；白名单同时拒绝引号外的 shell 元字符
以防拼接注入（引号内的元字符为程序参数，如 python -c "import time; ..."）。
"""
from __future__ import annotations

import os
import shlex
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass

from pydantic import BaseModel

from ..config import Settings


class SandboxResult(BaseModel):
    ok: bool
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0
    blocked: bool = False
    reason: str = ""


@dataclass
class SandboxExecutor(ABC):
    timeout_seconds: float = 30.0

    @abstractmethod
    def execute(self, command: str) -> SandboxResult: ...


class LocalSubprocessSandbox(SandboxExecutor):
    """受限本地子进程：命令前缀必须命中白名单，超时强制终止。"""

    # shell 元字符（Windows cmd 与 POSIX 均需拒绝，防拼接注入）
    _META_CHARS = set('&|<>^%!()')

    @staticmethod
    def _has_unquoted_meta(command: str) -> bool:
        """判断字符串中是否存在引号外的 shell 元字符。"""
        in_single = False
        in_double = False
        for ch in command:
            if ch == "'" and not in_double:
                in_single = not in_single
            elif ch == '"' and not in_single:
                in_double = not in_double
            elif not in_single and not in_double and ch in LocalSubprocessSandbox._META_CHARS:
                return True
        return False

    def __init__(self, settings: Settings) -> None:
        super().__init__(timeout_seconds=settings.sandbox_timeout_seconds)
        self._allowed = settings.sandbox_allowed_commands

    def _check_allowed(self, command: str) -> str | None:
        cmd = command.strip()
        if not cmd:
            return "empty command"
        if self._has_unquoted_meta(cmd):
            return f"shell metacharacters not allowed: {cmd}"
        for prefix in self._allowed:
            if cmd.startswith(prefix):
                return None
        return f"command not in whitelist: {cmd.split()[0] if cmd.split() else cmd}"

    def execute(self, command: str) -> SandboxResult:
        reason = self._check_allowed(command)
        if reason is not None:
            return SandboxResult(ok=False, blocked=True, reason=reason, returncode=-1)

        # Windows：echo/type 等为 cmd 内建命令，无独立 exe，统一经 cmd.exe 执行；
        # POSIX：shlex 分词后直执行（保持无 shell 解析，白名单已拦截元字符）。
        if os.name == "nt":
            argv = [os.environ.get("ComSpec", "cmd.exe"), "/d", "/s", "/c", command]
        else:
            argv = shlex.split(command)

        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
            return SandboxResult(
                ok=proc.returncode == 0,
                stdout=proc.stdout,
                stderr=proc.stderr,
                returncode=proc.returncode,
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(ok=False, stderr="timeout expired", returncode=-2)
        except FileNotFoundError as exc:
            return SandboxResult(ok=False, stderr=str(exc), returncode=-3)
