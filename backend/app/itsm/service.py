"""ITSM 工单引擎：Repository 与审批状态机（应用服务层）。

提供工单 CRUD、状态流转、审批任务创建/决策、Agent 自动建单与知识沉淀回调。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ApprovalTask, Ticket

_VALID_TICKET_STATUS = {"open", "in_progress", "resolved", "closed"}
_VALID_APPROVAL_STATUS = {"pending", "approved", "rejected"}


class TicketConflictError(Exception):
    """非法状态流转。"""


class ApprovalNotPendingError(Exception):
    """只能决策 pending 状态的审批任务。"""


def _narrate(status: str) -> str:
    return {"open": "已创建", "in_progress": "处理中",
            "resolved": "已解决", "closed": "已关闭"}.get(status, status)


class ITSMService:
    """封装工单与审批的业务规则，Session 由调用方/依赖注入提供。"""

    def __init__(self, autoheal_high_risk_requires_approval: bool = True) -> None:
        self._high_risk_requires_approval = autoheal_high_risk_requires_approval

    # ---------- 工单 ----------
    def create_ticket(self, session: Session, *, ticket_type: str = "incident",
                      title: str, description: str = "", source: str = "manual",
                      source_agent_id: str | None = None,
                      autoheal_run_id: int | None = None) -> Ticket:
        ticket = Ticket(
            ticket_type=ticket_type, title=title, description=description,
            status="open", source=source, source_agent_id=source_agent_id,
            autoheal_run_id=autoheal_run_id,
        )
        session.add(ticket)
        session.flush()
        return ticket

    def get_ticket(self, session: Session, ticket_id: int) -> Ticket | None:
        return session.get(Ticket, ticket_id)

    def list_tickets(self, session: Session, *, status: str | None = None,
                     limit: int = 100) -> list[Ticket]:
        stmt = select(Ticket).order_by(Ticket.created_at.desc()).limit(limit)
        if status:
            stmt = stmt.where(Ticket.status == status)
        return list(session.scalars(stmt))

    def transition_ticket(self, session: Session, ticket_id: int,
                          to_status: str, actor: str = "system") -> Ticket:
        if to_status not in _VALID_TICKET_STATUS:
            raise TicketConflictError(f"illegal ticket status: {to_status}")
        ticket = session.get(Ticket, ticket_id)
        if ticket is None:
            raise KeyError(f"ticket not found: {ticket_id}")
        ticket.status = to_status
        if to_status == "resolved":
            ticket.resolved_at = datetime.now(timezone.utc)
        return ticket

    def add_knowledge_feedback(self, session: Session, ticket_id: int, text: str,
                               knowledge_service) -> None:  # noqa: ANN001
        """ITSM 处置记录自动沉淀为知识（对应 PRD ITSM-06 / AIOPS 交互）。"""
        ticket = session.get(Ticket, ticket_id)
        if ticket is None:
            raise KeyError(f"ticket not found: {ticket_id}")
        doc_id = f"ticket-{ticket.id}"
        knowledge_service.add_document(
            doc_id=doc_id, text=text,
            metadata={"source": "itsm", "ticket_id": ticket.id,
                      "title": ticket.title},
        )

    # ---------- 审批流 ----------
    def create_approval(self, session: Session, ticket_id: int, *, tool_id: str,
                        action_summary: str, risk_level: str,
                        params: dict | None = None) -> ApprovalTask:
        task = ApprovalTask(
            ticket_id=ticket_id,
            tool_id=tool_id,
            action_summary=action_summary,
            risk_level=risk_level,
            params_json=json.dumps(params or {}, ensure_ascii=False),
            status="pending",
        )
        session.add(task)
        session.flush()
        return task

    def get_approval(self, session: Session, approval_id: int) -> ApprovalTask | None:
        return session.get(ApprovalTask, approval_id)

    def list_pending_approvals(self, session: Session) -> list[ApprovalTask]:
        stmt = select(ApprovalTask).where(
            ApprovalTask.status == "pending").order_by(ApprovalTask.created_at.asc())
        return list(session.scalars(stmt))

    def decide_approval(self, session: Session, approval_id: int, *,
                        approve: bool, actor: str,
                        comment: str | None = None) -> ApprovalTask:
        task = session.get(ApprovalTask, approval_id)
        if task is None:
            raise KeyError(f"approval task not found: {approval_id}")
        if task.status != "pending":
            raise ApprovalNotPendingError(
                f"approval task not pending: {task.status}")
        task.status = "approved" if approve else "rejected"
        task.decided_by = actor
        task.decision_comment = comment
        task.decided_at = datetime.now(timezone.utc)
        return task

    # 将操作参数快照解析回 dict
    @staticmethod
    def approval_params(task: ApprovalTask) -> dict:
        return json.loads(task.params_json or "{}")


def ticket_as_dict(t: Ticket) -> dict:
    """序列化工单（含审批任务）。"""
    return {
        "id": t.id,
        "ticket_type": t.ticket_type,
        "title": t.title,
        "description": t.description,
        "status": t.status,
        "status_label": _narrate(t.status),
        "source": t.source,
        "source_agent_id": t.source_agent_id,
        "autoheal_run_id": t.autoheal_run_id,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "resolved_at": t.resolved_at.isoformat() if t.resolved_at else None,
        "approvals": [approval_as_dict(a) for a in t.approvals],
    }


def approval_as_dict(a: ApprovalTask) -> dict:
    return {
        "id": a.id,
        "ticket_id": a.ticket_id,
        "tool_id": a.tool_id,
        "action_summary": a.action_summary,
        "risk_level": a.risk_level,
        "params": json.loads(a.params_json or "{}"),
        "status": a.status,
        "decided_by": a.decided_by,
        "decision_comment": a.decision_comment,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "decided_at": a.decided_at.isoformat() if a.decided_at else None,
    }
