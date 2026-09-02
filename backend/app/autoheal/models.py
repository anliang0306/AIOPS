"""故障自愈执行记录（AutohealRun）持久化模型。"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db.session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AutohealRun(Base):
    """一次故障自愈执行记录，串联工单 / 审批 / 执行 / 验证 / 回滚结果。"""

    __tablename__ = "autoheal_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident: Mapped[str] = mapped_column(String(255))          # 故障/告警描述
    ticket_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 机器可读状态：created/diagnosed/approved/executed/succeeded/failed/rolled_back/needs_human
    status: Mapped[str] = mapped_column(String(20), default="created")
    diagnosis: Mapped[str] = mapped_column(Text, default="")
    action_plan: Mapped[str] = mapped_column(Text, default="[]")  # JSON 计划
    execution_result: Mapped[str] = mapped_column(Text, default="{}")
    verify_result: Mapped[str] = mapped_column(Text, default="{}")
    rolled_back: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
