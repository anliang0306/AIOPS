"""Agent 编排 API：生命周期管理与任务执行。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..agents.base import AgentStatus
from ..agents.registry import AgentRegistry
from ..deps import get_agent_registry

router = APIRouter(prefix="/agents", tags=["agents"])


class AgentRunRequest(BaseModel):
    payload: dict[str, Any] = {}


@router.get("")
def list_agents(status: AgentStatus | None = None,
                registry: AgentRegistry = Depends(get_agent_registry)) -> dict:
    return {"agents": registry.list(status=status)}


@router.post("/{agent_id}/start")
def start_agent(agent_id: str, registry: AgentRegistry = Depends(get_agent_registry)) -> dict:
    try:
        agent = registry.start(agent_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"agent_id": agent.agent_id, "status": agent.status.value}


@router.post("/{agent_id}/stop")
def stop_agent(agent_id: str, registry: AgentRegistry = Depends(get_agent_registry)) -> dict:
    try:
        agent = registry.stop(agent_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"agent_id": agent.agent_id, "status": agent.status.value}


@router.post("/{agent_id}/run")
def run_agent(agent_id: str, req: AgentRunRequest,
              registry: AgentRegistry = Depends(get_agent_registry)) -> dict:
    try:
        result = registry.run(agent_id, req.payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return result.model_dump()
