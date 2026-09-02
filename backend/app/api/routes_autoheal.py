"""故障自愈 API：触发自愈、查询执行记录、查看待审批与执行批准的动作。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ..db.session import Database
from ..deps import get_database
from ..itsm.service import ITSMService, approval_as_dict
from ..tools.registry import ToolRegistry
from ..autoheal.models import AutohealRun

router = APIRouter(prefix="/autoheal", tags=["autoheal"])


class AutohealRequest(BaseModel):
    incident: str


def _get_itsm(request: Request) -> ITSMService:
    # 从 app.state 取共享 ITSMService（与 Agent 相同实例，保持配置一致）
    return request.app.state.itsm


@router.post("/run")
def run_autoheal(req: AutohealRequest, request: Request,
                 db: Database = Depends(get_database)) -> dict:
    if not req.incident.strip():
        raise HTTPException(status_code=400, detail="incident 不能为空")
    agent = request.app.state.agent_registry.get("autoheal-agent")
    if agent is None:
        raise HTTPException(status_code=500, detail="autoheal-agent 未注册")
    # 使用独立 Session（Agent 内部提交事务）
    session = db.new_session()
    try:
        run = agent._run(session, req.incident)  # noqa: SLF001 - 内部业务方法
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise HTTPException(status_code=500, detail=f"故障自愈执行失败: {exc}") from exc
    finally:
        session.close()
    return autoheal_run_as_dict(run)


@router.get("/runs/{run_id}")
def get_run(run_id: int, db: Database = Depends(get_database)) -> dict:
    from sqlalchemy import select
    with db.session_scope() as session:
        run = session.get(AutohealRun, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
        return autoheal_run_as_dict(run)


def autoheal_run_as_dict(run: AutohealRun) -> dict:
    import json
    return {
        "run_id": run.id,
        "incident": run.incident,
        "ticket_id": run.ticket_id,
        "status": run.status,
        "diagnosis": run.diagnosis,
        "action_plan": _safe_json(run.action_plan),
        "execution_result": _safe_json(run.execution_result),
        "verify_result": _safe_json(run.verify_result),
        "rolled_back": run.rolled_back,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


def _safe_json(raw: str):
    import json
    try:
        return json.loads(raw or "null")
    except json.JSONDecodeError:
        return raw
