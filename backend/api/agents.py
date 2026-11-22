from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Agent
from db.session import get_db
from governance.audit import log_event

router = APIRouter(prefix="/agents", tags=["agents"])

VALID_STATUSES = {"active", "suspended", "deactivated"}


@router.get("")
def list_agents(db: Session = Depends(get_db)):
    agents = db.execute(select(Agent)).scalars().all()
    return {"agents": [_agent_to_dict(a) for a in agents]}


@router.get("/{agent_id}")
def get_agent(agent_id: str, db: Session = Depends(get_db)):
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(404, "Agent not found")
    return _agent_to_dict(agent)


class StatusUpdate(BaseModel):
    status: str


@router.patch("/{agent_id}/status")
def update_agent_status(agent_id: str, body: StatusUpdate, db: Session = Depends(get_db)):
    if body.status not in VALID_STATUSES:
        raise HTTPException(400, f"status must be one of {VALID_STATUSES}")
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(404, "Agent not found")

    old_status = agent.status
    agent.status = body.status
    db.commit()

    log_event(
        db,
        event_type="agent_status_change",
        agent_id=agent.id,
        requested_action=f"set_status:{body.status}",
        policy_evaluated="kill-switch",
        decision="ALLOW",
        reason=f"Agent '{agent.name}' status changed from '{old_status}' to '{body.status}' by the user.",
    )
    return _agent_to_dict(agent)


def _agent_to_dict(a: Agent) -> dict:
    return {
        "id": a.id,
        "slug": a.slug,
        "name": a.name,
        "description": a.description,
        "purpose": a.purpose,
        "owner": a.owner,
        "status": a.status,
        "permitted_tools": a.permitted_tools,
        "restricted_actions": a.restricted_actions,
        "permissions": [
            {"resource_type": p.resource_type, "resource_value": p.resource_value, "access_level": p.access_level}
            for p in a.permissions
        ],
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }
