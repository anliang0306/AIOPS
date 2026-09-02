"""ITSM 工单引擎服务层：工单 CRUD/状态流转、审批状态机、非法流转。"""
from __future__ import annotations

import pytest

from app.itsm.service import ITSMService, TicketConflictError, ApprovalNotPendingError


def test_create_and_get_ticket(database, itsm):  # noqa: ANN001
    with database.session_scope() as session:
        t = itsm.create_ticket(session, title="服务器502", description="后端不可用")
        tid = t.id
        assert t.status == "open"
        assert itsm.get_ticket(session, tid).title == "服务器502"


def test_list_tickets_filter(database, itsm):  # noqa: ANN001
    with database.session_scope() as session:
        itsm.create_ticket(session, title="a")
        itsm.create_ticket(session, title="b")
        itsm.create_ticket(session, title="c")
    with database.session_scope() as session:
        assert len(itsm.list_tickets(session)) == 3
        assert len(itsm.list_tickets(session, status="open")) == 3


def test_transition_ticket_lifecycle(database, itsm):  # noqa: ANN001
    with database.session_scope() as session:
        t = itsm.create_ticket(session, title="x")
        itsm.transition_ticket(session, t.id, "in_progress")
        itsm.transition_ticket(session, t.id, "resolved", actor="sre")
        got = itsm.get_ticket(session, t.id)
        assert got.status == "resolved"
        assert got.resolved_at is not None


def test_transition_illegal_status_raises(database, itsm):  # noqa: ANN001
    with database.session_scope() as session:
        t = itsm.create_ticket(session, title="x")
        with pytest.raises(TicketConflictError):
            itsm.transition_ticket(session, t.id, "nonsense")


def test_approval_state_machine(database, itsm):  # noqa: ANN001
    with database.session_scope() as session:
        t = itsm.create_ticket(session, title="审批测试")
        task = itsm.create_approval(
            session, t.id, tool_id="shell", action_summary="重启服务",
            risk_level="high", params={"command": "echo restart"})
        assert task.status == "pending"

        # 非法决策：重复决策
        itsm.decide_approval(session, task.id, approve=True, actor="ops")
        with pytest.raises(ApprovalNotPendingError):
            itsm.decide_approval(session, task.id, approve=False, actor="ops")

        new_t = itsm.get_ticket(session, t.id)
        approved = {a.id: a.status for a in new_t.approvals}
        assert approved[task.id] == "approved"


def test_reject_approval(database, itsm):  # noqa: ANN001
    with database.session_scope() as session:
        t = itsm.create_ticket(session, title="拒绝")
        task = itsm.create_approval(session, t.id, tool_id="x", action_summary="y",
                                    risk_level="medium")
        itsm.decide_approval(session, task.id, approve=False, actor="auditor",
                             comment="拒绝")
        assert task.status == "rejected"
        assert itsm.list_pending_approvals(session) == []


def test_approval_params_roundtrip(database, itsm):  # noqa: ANN001
    with database.session_scope() as session:
        t = itsm.create_ticket(session, title="参数")
        task = itsm.create_approval(
            session, t.id, tool_id="shell", action_summary="cmd",
            risk_level="low", params={"command": "echo hi", "flag": 1})
        parsed = itsm.approval_params(task)
        assert parsed == {"command": "echo hi", "flag": 1}


def test_approval_creation_requires_low_direct(database, itsm):  # noqa: ANN001
    """中高风险强制审批（通过 create_approval 显式走审批；低风险动作由 Agent 判断直接执行）。"""
    with database.session_scope() as session:
        t = itsm.create_ticket(session, title="低风险验证")
        task = itsm.create_approval(session, t.id, tool_id="shell",
                                    action_summary="echo", risk_level="low")
        assert task.risk_level == "low"
