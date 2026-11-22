from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Agent, Approval, Memory
from db.session import get_db
from governance.audit import log_event
from memory.engine import index_memory

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("")
def list_approvals(status: str | None = None, db: Session = Depends(get_db)):
    stmt = select(Approval).order_by(Approval.created_at.desc())
    if status:
        stmt = stmt.where(Approval.status == status)
    approvals = db.execute(stmt).scalars().all()
    agents = {a.id: a.name for a in db.execute(select(Agent)).scalars()}
    return {"approvals": [_approval_to_dict(a, agents) for a in approvals]}


@router.get("/{approval_id}")
def get_approval(approval_id: str, db: Session = Depends(get_db)):
    approval = db.get(Approval, approval_id)
    if approval is None:
        raise HTTPException(404, "Approval not found")
    agents = {a.id: a.name for a in db.execute(select(Agent)).scalars()}
    payload = _approval_to_dict(approval, agents)
    if approval.resource_type == "memory" and approval.resource_id:
        memory = db.get(Memory, approval.resource_id)
        if memory is not None:
            payload["resource_preview"] = {
                "memory_type": memory.memory_type,
                "title": memory.title,
                "description": memory.description,
                "topic": memory.topic,
            }
    return payload


class DecisionRequest(BaseModel):
    decision: str  # "approve" | "reject"
    decided_by: str = "user"


@router.post("/{approval_id}/decide")
def decide_approval(approval_id: str, req: DecisionRequest, db: Session = Depends(get_db)):
    if req.decision not in ("approve", "reject"):
        raise HTTPException(400, "decision must be 'approve' or 'reject'")
    approval = db.get(Approval, approval_id)
    if approval is None:
        raise HTTPException(404, "Approval not found")
    if approval.status != "pending":
        raise HTTPException(400, f"Approval already decided (status: {approval.status})")

    approval.status = "approved" if req.decision == "approve" else "rejected"
    approval.decided_by = req.decided_by
    approval.decided_at = datetime.now(timezone.utc)

    # Apply the decision to the underlying resource. An approval request is
    # only a request — denying it must never execute the action it covers.
    if approval.resource_type == "memory" and approval.resource_id:
        memory = db.get(Memory, approval.resource_id)
        if memory is not None:
            memory.approval_status = "approved" if req.decision == "approve" else "rejected"
            if req.decision == "approve":
                index_memory(memory)

    db.commit()

    log_event(
        db,
        event_type="human_approval" if req.decision == "approve" else "human_rejection",
        agent_id=approval.agent_id,
        resource_id=approval.resource_id,
        requested_action=approval.action,
        policy_evaluated=approval.policy_id,
        decision="ALLOW" if req.decision == "approve" else "DENY",
        reason=f"Human {req.decision}d: {approval.reason}",
        approval_ref=approval.id,
    )

    agents = {a.id: a.name for a in db.execute(select(Agent)).scalars()}
    return _approval_to_dict(approval, agents)


def _approval_to_dict(a: Approval, agents: dict[str, str]) -> dict:
    return {
        "id": a.id,
        "agent_id": a.agent_id,
        "agent_name": agents.get(a.agent_id, a.agent_id),
        "action": a.action,
        "resource_type": a.resource_type,
        "resource_id": a.resource_id,
        "reason": a.reason,
        "policy_id": a.policy_id,
        "status": a.status,
        "decided_by": a.decided_by,
        "decided_at": a.decided_at.isoformat() if a.decided_at else None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }
