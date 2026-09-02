"""故障自愈 Agent：检测 -> 诊断 -> 审批门禁 -> 执行 -> 验证 -> 回滚 -> 知识沉淀。

设计要点（对齐 PRD SEC-04）：
- 低风险动作直接执行；中/高风险动作创建 ITSM 审批任务，拒绝时不执行。
- 执行失败时按风险策略尝试回滚（骨架记录回滚意图）。
- 处置记录沉淀为知识库条目（ITSM 处理反馈）。
- 遵循 BaseAgent 契约 execute(payload)->AgentRunResult；Session 通过 __init__ 注入的
  session_provider（0 参可调用对象）获取，保证注册表 run 也能在 DB 环境下工作。
"""
from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from ..agents.base import AgentRunResult, BaseAgent
from ..itsm.service import ITSMService
from ..rag.service import KnowledgeService
from ..tools.base import BaseTool, RiskLevel
from ..tools.registry import ToolRegistry
from .models import AutohealRun


class AutohealAgent(BaseAgent):
    """故障自愈 Agent（依赖注入 Session 提供器 / 工具 / ITSM / RAG）。"""

    _RULES: dict[str, dict[str, Any]] = {
        "502": {"verdict": "后端服务不可用", "plan": [("shell", {"command": "echo restart backend"}, "medium")]},
        "disk_full": {"verdict": "磁盘空间不足", "plan": [("shell", {"command": "echo cleanup /var/log"}, "medium")]},
        "service_down": {"verdict": "服务进程异常", "plan": [("shell", {"command": "echo restart service"}, "medium")]},
    }

    def __init__(self, itsm: ITSMService, tools: ToolRegistry,
                 knowledge: KnowledgeService,
                 session_provider: Callable[[], Session]) -> None:
        super().__init__(
            agent_id="autoheal-agent",
            name="故障自愈 Agent",
            description="对故障告警进行诊断、审批门禁下的自动化处置、验证与回滚",
            version="0.2.0",
        )
        self._itsm = itsm
        self._tools = tools
        self._knowledge = knowledge
        self._session_provider = session_provider

    # ---- 基类契约 ----
    def execute(self, payload: dict[str, Any]) -> AgentRunResult:  # noqa: ANN401
        try:
            incident = (payload.get("incident") or "").strip()
            if not incident:
                raise ValueError("缺少 incident（故障描述）")
            with self._session_provider() as session:
                run = self._run(session, incident)
            return AgentRunResult(
                agent_id=self.agent_id, ok=run.status == "succeeded",
                summary=f"故障自愈完成: {run.status}",
                details={"status": run.status, "run_id": run.id,
                         "ticket_id": run.ticket_id, "diagnosis": run.diagnosis},
            )
        except Exception as exc:  # noqa: BLE001
            self.status.value  # noqa: B018  # 保持生命周期字段可访问
            return AgentRunResult(agent_id=self.agent_id, ok=False, summary=f"自愈执行失败: {exc}")

    # ---- 核心流程（带 Session）----
    def _run(self, session: Session, incident: str) -> AutohealRun:
        run = AutohealRun(incident=incident, status="created")
        session.add(run)
        session.flush()

        verdict, plan = self._diagnose(incident)
        run.diagnosis = verdict
        run.action_plan = json.dumps(plan, ensure_ascii=False)
        run.status = "diagnosed"
        session.flush()

        ticket = self._itsm.create_ticket(
            session, ticket_type="incident", title=f"故障自愈: {incident[:60]}",
            description=f"诊断: {verdict}",
            source="autoheal-agent", source_agent_id=self.agent_id,
            autoheal_run_id=run.id,
        )
        run.ticket_id = ticket.id
        session.flush()

        results = self._execute_plan(session, ticket.id, plan)
        run.execution_result = json.dumps(results, ensure_ascii=False)

        pending = [r for r in results if r.get("result") == "pending_approval"]
        executed_ok = [r for r in results if r.get("result") == "executed" and r.get("ok")]
        executed_fail = [r for r in results if r.get("result") == "executed" and not r.get("ok")]

        if executed_fail:
            run.rolled_back = True
            run.status = "rolled_back"
            run.verify_result = json.dumps({"note": "执行失败，触发回滚预案（骨架记录回滚意图）"},
                                           ensure_ascii=False)
            self._itsm.transition_ticket(session, ticket.id, "in_progress", actor=self.agent_id)
        elif pending:
            run.status = "needs_human"
            self._itsm.transition_ticket(session, ticket.id, "in_progress", actor=self.agent_id)
        elif executed_ok:
            run.status = "succeeded"
            run.verify_result = json.dumps({"verified": True}, ensure_ascii=False)
            self._itsm.transition_ticket(session, ticket.id, "resolved", actor=self.agent_id)
        else:
            run.status = "needs_human"
            self._itsm.transition_ticket(session, ticket.id, "in_progress", actor=self.agent_id)

        if run.status in ("succeeded", "rolled_back"):
            self._itsm.add_knowledge_feedback(
                session, ticket.id,
                f"[自愈] {incident}\n诊断: {verdict}\n结果: {run.status}", self._knowledge)

        session.commit()
        session.refresh(run)
        return run

    def _execute_plan(self, session: Session, ticket_id: int,
                      plan: list[tuple]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for tool_id, params, risk in plan:
            tool: BaseTool | None = self._tools.get(tool_id)
            if tool is None:
                results.append({"tool": tool_id, "result": "skipped: tool not found"})
                continue
            if self._needs_approval(tool, risk):
                task = self._itsm.create_approval(
                    session, ticket_id, tool_id=tool_id,
                    action_summary=f"{tool.spec.name}: {params.get('command', '')}",
                    risk_level=risk, params=params,
                )
                results.append({"tool": tool_id, "result": "pending_approval",
                                "approval_id": task.id, "risk_level": risk})
            else:
                r = tool.run(**params)
                results.append({"tool": tool_id, "result": "executed",
                                "ok": r.ok, "output": r.output[:200]})
        return results

    def _diagnose(self, incident: str) -> tuple[str, list[tuple]]:
        low = incident.lower()
        for key, rule in self._RULES.items():
            if key in low:
                return rule["verdict"], list(rule["plan"])
        return "未识别故障模式，建议转人工排查", []

    def _needs_approval(self, tool: BaseTool, risk: str) -> bool:
        # 只要动作风险达 medium/high，或工具本身为 medium/high，一律走审批门禁。
        # （对齐 PRD SEC-04：中高风险动作强制人工审批）
        level = RiskLevel(risk)
        if level in (RiskLevel.MEDIUM, RiskLevel.HIGH):
            return True
        if tool.spec.risk_level in (RiskLevel.HIGH, RiskLevel.MEDIUM):
            return True
        high_only = self._itsm._high_risk_requires_approval  # noqa: SLF001
        return level == RiskLevel.HIGH and high_only
