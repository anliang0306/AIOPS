"""ITSM 工单引擎 API：工单 CRUD/状态、审批任务查询/决策、知识沉淀。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ..db.session import Database
from ..deps import get_database, get_knowledge
from ..itsm.service import (
    ITSMService, TicketConflictError, approval_as_dict, ticket_as_dict,
    ApprovalNotPendingError,
)
from ..rag.service import KnowledgeService

router = APIRouter(prefix="/itsm", tags=["itsm"])


class TicketCreate(BaseModel):
    ticket_type: str = "incident"
    title: str
    description: str = ""
    source: str = "manual"
    source_agent_id: str | None = None


class TicketTransition(BaseModel):
    to_status: str
    actor: str = "manual"


class ApprovalDecision(BaseModel):
    approve: bool
    actor: str
    comment: str | None = None


class KnowledgeFeedback(BaseModel):
    text: str


def _service(db: Database = Depends(get_database)) -> ITSMService:
    return ITSMService(autoheal_high_risk_requires_approval=True)


@router.post("")
def create_ticket(req: TicketCreate, db: Database = Depends(get_database),
                  service: ITSMService = Depends(_service)) -> dict:
    with db.session_scope() as session:
        t = service.create_ticket(
            session, ticket_type=req.ticket_type, title=req.title,
            description=req.description, source=req.source,
            source_agent_id=req.source_agent_id)
        return ticket_as_dict(t)


@router.get("")
def list_tickets(status: str | None = None, limit: int = 100,
                 db: Database = Depends(get_database),
                 service: ITSMService = Depends(_service)) -> dict:
    with db.session_scope() as session:
        return {"tickets": [ticket_as_dict(t) for t in service.list_tickets(
            session, status=status, limit=limit)]}


@router.get("/{ticket_id}")
def get_ticket(ticket_id: int, db: Database = Depends(get_database),
               service: ITSMService = Depends(_service)) -> dict:
    with db.session_scope() as session:
        t = service.get_ticket(session, ticket_id)
        if t is None:
            raise HTTPException(status_code=404, detail=f"ticket not found: {ticket_id}")
        return ticket_as_dict(t)


@router.post("/{ticket_id}/transition")
def transition(ticket_id: int, req: TicketTransition,
               db: Database = Depends(get_database),
               service: ITSMService = Depends(_service)) -> dict:
    with db.session_scope() as session:
        try:
            t = service.transition_ticket(session, ticket_id, req.to_status, req.actor)
        except TicketConflictError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return ticket_as_dict(t)


@router.get("/approvals/pending")
def list_pending(db: Database = Depends(get_database),
                 service: ITSMService = Depends(_service)) -> dict:
    with db.session_scope() as session:
        return {"approvals": [approval_as_dict(a) for a in
                              service.list_pending_approvals(session)]}


@router.post("/approvals/{approval_id}/decide")
def decide(approval_id: int, req: ApprovalDecision,
           db: Database = Depends(get_database),
           service: ITSMService = Depends(_service)) -> dict:
    with db.session_scope() as session:
        try:
            task = service.decide_approval(
                session, approval_id, approve=req.approve,
                actor=req.actor, comment=req.comment)
        except ApprovalNotPendingError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return approval_as_dict(task)


@router.post("/{ticket_id}/knowledge")
def add_knowledge(ticket_id: int, req: KnowledgeFeedback,
                  request: Request,
                  db: Database = Depends(get_database),
                  service: ITSMService = Depends(_service),
                  kb: KnowledgeService = Depends(get_knowledge)) -> dict:
    with db.session_scope() as session:
        try:
            service.add_knowledge_feedback(session, ticket_id, req.text, kb)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"ok": True, "ticket_id": ticket_id}
