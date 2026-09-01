"""沙箱执行环境。

骨架阶段实现：白名单命令 + 超时限制的本地受限子进程（LocalSubprocessSandbox），
用于演示与测试。生产环境必须切换为容器沙箱（DockerSandbox，见 docs/architecture.md）：
限制文件系统 / 网络 / CPU / 内存配额，高风险命令直接拦截。
"""
from __future__ import annotations

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

    def __init__(self, settings: Settings) -> None:
        super().__init__(timeout_seconds=settings.sandbox_timeout_seconds)
        self._allowed = settings.sandbox_allowed_commands

    def _check_allowed(self, command: str) -> str | None:
        cmd = command.strip()
        if not cmd:
            return "empty command"
        for prefix in self._allowed:
            if cmd.startswith(prefix):
                return None
        return f"command not in whitelist: {cmd.split()[0] if cmd.split() else cmd}"

    def execute(self, command: str) -> SandboxResult:
        reason = self._check_allowed(command)
        if reason is not None:
            return SandboxResult(ok=False, blocked=True, reason=reason, returncode=-1)

        try:
            proc = subprocess.run(
                shlex.split(command),
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
