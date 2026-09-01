"""Agent 基类与生命周期状态。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic import BaseModel


class AgentStatus(str, Enum):
    REGISTERED = "registered"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"


class AgentRunResult(BaseModel):
    agent_id: str
    ok: bool
    summary: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class BaseAgent(ABC):
    agent_id: str
    name: str
    description: str = ""
    status: AgentStatus = AgentStatus.REGISTERED
    version: str = "0.1.0"

    @abstractmethod
    def execute(self, payload: dict[str, Any]) -> AgentRunResult:
        """执行一次 Agent 任务；实现方负责异常捕获并返回 AgentRunResult。"""
