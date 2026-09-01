"""CLI 工具封装引擎 API：工具列表、执行（含风险等级返回，前端可据此触发审批）。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..deps import get_tool_registry
from ..tools.base import RiskLevel
from ..tools.registry import ToolRegistry

router = APIRouter(prefix="/tools", tags=["tools"])


class ToolExecRequest(BaseModel):
    tool_id: str
    params: dict[str, Any] = {}
    # 审批令牌：骨架阶段置 true 表示"已获人工审批"；中高风险工具默认要求
    approved: bool = False


@router.get("")
def list_tools(max_risk: RiskLevel | None = None,
               registry: ToolRegistry = Depends(get_tool_registry)) -> dict:
    return {"tools": registry.list(max_risk=max_risk)}


@router.post("/execute")
def execute_tool(req: ToolExecRequest,
                 registry: ToolRegistry = Depends(get_tool_registry)) -> dict:
    tool = registry.get(req.tool_id)
    if tool is None:
        raise HTTPException(status_code=404, detail=f"tool not found: {req.tool_id}")
    if tool.require_approval and not req.approved:
        raise HTTPException(
            status_code=403,
            detail={"error": "需要人工审批", "tool": tool.describe(),
                    "hint": "中高风险操作须经人工审批，设置 approved=true 表示审批通过"},
        )
    try:
        result = tool.run(**req.params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result.model_dump()
