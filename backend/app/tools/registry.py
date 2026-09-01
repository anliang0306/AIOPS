"""工具注册表：注册、查询、按风险等级过滤。"""
from __future__ import annotations

from typing import Any

from .base import BaseTool, RiskLevel


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        if tool.spec.id in self._tools:
            raise ValueError(f"tool already registered: {tool.spec.id}")
        self._tools[tool.spec.id] = tool

    def get(self, tool_id: str) -> BaseTool | None:
        return self._tools.get(tool_id)

    def require(self, tool_id: str) -> BaseTool:
        tool = self.get(tool_id)
        if tool is None:
            raise KeyError(f"tool not found: {tool_id}")
        return tool

    def list(self, max_risk: RiskLevel | None = None) -> list[dict[str, Any]]:
        items = []
        for t in self._tools.values():
            if max_risk is None or _rank(t.spec.risk_level) <= _rank(max_risk):
                items.append(t.describe())
        return sorted(items, key=lambda d: d["id"])


def _rank(level: RiskLevel) -> int:
    return {RiskLevel.LOW: 1, RiskLevel.MEDIUM: 2, RiskLevel.HIGH: 3}[level]
