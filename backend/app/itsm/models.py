"""ITSM 工单引擎 ORM 模型：工单（Ticket）与审批任务（ApprovalTask）。

实现 PRD AI+ITSM 平台核心：事件/变更工单全生命周期 + 中高风险操作审批流。
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Ticket(Base):
    """ITSM 工单：覆盖事件单（incident）与变更单（change）处置。"""

    __tablename__ = "itsm_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_type: Mapped[str] = mapped_column(String(16), default="incident")  # incident / change
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    # 生命周期：open -> in_progress -> resolved -> closed
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    # 生成来源：manual / autoheal-agent / monitor
    source: Mapped[str] = mapped_column(String(32), default="manual")
    source_agent_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 关联的故障自愈执行记录主键（见 autoheal 模块）
    autoheal_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    approvals: Mapped[list["ApprovalTask"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan")


class ApprovalTask(Base):
    """审批任务：中高风险 Agent 操作在沙箱执行前须经人工确认。

    状态机：pending -> approved / rejected。审批记录持久化留存（对应 PRD SEC-04）。
    """

    __tablename__ = "itsm_approval_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("itsm_tickets.id", ondelete="CASCADE"), index=True)
    # 待执行的工具/操作
    tool_id: Mapped[str] = mapped_column(String(64))
    action_summary: Mapped[str] = mapped_column(String(255))
    risk_level: Mapped[str] = mapped_column(String(16), default="medium")  # low/medium/high
    # 供执行的参数快照（JSON）
    params_json: Mapped[str] = mapped_column(Text, default="{}")
    # 状态机字段
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending/approved/rejected
    decided_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decision_comment: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    ticket: Mapped[Ticket] = relationship(back_populates="approvals")
