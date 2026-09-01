"""Agent 注册表：注册、生命周期启停、按状态过滤。"""
from __future__ import annotations

from typing import Any

from .base import AgentRunResult, AgentStatus, BaseAgent


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        if agent.agent_id in self._agents:
            raise ValueError(f"agent already registered: {agent.agent_id}")
        self._agents[agent.agent_id] = agent

    def get(self, agent_id: str) -> BaseAgent | None:
        return self._agents.get(agent_id)

    def require(self, agent_id: str) -> BaseAgent:
        agent = self.get(agent_id)
        if agent is None:
            raise KeyError(f"agent not found: {agent_id}")
        return agent

    def start(self, agent_id: str) -> BaseAgent:
        agent = self.require(agent_id)
        agent.status = AgentStatus.RUNNING
        return agent

    def stop(self, agent_id: str) -> BaseAgent:
        agent = self.require(agent_id)
        agent.status = AgentStatus.STOPPED
        return agent

    def run(self, agent_id: str, payload: dict[str, Any]) -> AgentRunResult:
        """执行 Agent 任务：RUNNING 状态才允许执行。"""
        agent = self.require(agent_id)
        if agent.status != AgentStatus.RUNNING:
            return AgentRunResult(
                agent_id=agent_id, ok=False,
                summary=f"agent not running (status={agent.status.value})",
            )
        try:
            return agent.execute(payload)
        except Exception as exc:  # noqa: BLE001
            agent.status = AgentStatus.FAILED
            return AgentRunResult(agent_id=agent_id, ok=False, summary=f"agent error: {exc}")

    def list(self, status: AgentStatus | None = None) -> list[dict[str, Any]]:
        items = []
        for a in self._agents.values():
            if status is None or a.status is status:
                items.append({
                    "agent_id": a.agent_id,
                    "name": a.name,
                    "description": a.description,
                    "status": a.status.value,
                    "version": a.version,
                })
        return sorted(items, key=lambda d: d["agent_id"])
