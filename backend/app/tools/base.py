"""工具定义抽象：把运维命令封装为标准工具，标注风险等级供 Agent 调用。"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    """风险等级：低/中/高。中高风险操作强制人工审批。"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ToolParam(BaseModel):
    name: str
    type: str = "string"
    required: bool = True
    description: str = ""


class ToolSpec(BaseModel):
    id: str
    name: str
    description: str
    risk_level: RiskLevel = RiskLevel.LOW
    params: list[ToolParam] = Field(default_factory=list)
    # 人工审批策略：high/medium 默认强制；low 直接执行
    require_approval: bool = False


class ToolResult(BaseModel):
    ok: bool
    tool_id: str
    output: str = ""
    error: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class BaseTool(ABC):
    spec: ToolSpec

    def __init__(self) -> None:
        if not getattr(self, "spec", None):
            raise TypeError(f"{type(self).__name__} must define spec")

    @abstractmethod
    def run(self, **kwargs: Any) -> ToolResult:
        """执行工具。实现方负责校验参数并捕获异常返回 ToolResult(ok=False)。"""

    @property
    def require_approval(self) -> bool:
        return self.spec.require_approval or self.spec.risk_level in (
            RiskLevel.MEDIUM, RiskLevel.HIGH,
        )

    def describe(self) -> dict[str, Any]:
        return {
            "id": self.spec.id,
            "name": self.spec.name,
            "description": self.spec.description,
            "risk_level": self.spec.risk_level.value,
            "require_approval": self.require_approval,
            "params": [p.model_dump() for p in self.spec.params],
        }


def parse_args(spec: ToolSpec, **kwargs: Any) -> dict[str, Any]:
    """按 spec.params 校验并规整入参；缺必填参数抛 ValueError。"""
    out: dict[str, Any] = {}
    for p in spec.params:
        val = kwargs.get(p.name)
        if val is None:
            if p.required:
                raise ValueError(f"missing required param: {p.name}")
            continue
        out[p.name] = val
    return out


def json_out(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)
