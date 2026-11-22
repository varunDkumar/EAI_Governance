from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models import Agent, AgentPermission, Approval, AuditEvent, Policy
from db.session import get_db

router = APIRouter(prefix="/governance", tags=["governance"])


@router.get("/policies")
def list_policies(db: Session = Depends(get_db)):
    policies = db.execute(select(Policy).order_by(Policy.priority)).scalars().all()
    return {
        "policies": [
            {
                "id": p.id,
                "name": p.name,
                "resource_type": p.resource_type,
                "condition": p.condition,
                "effect": p.effect,
                "reason": p.reason,
                "priority": p.priority,
            }
            for p in policies
        ]
    }


@router.get("/overview")
def governance_overview(db: Session = Depends(get_db)):
    agents = db.execute(select(Agent)).scalars().all()
    by_status = {"active": 0, "suspended": 0, "deactivated": 0}
    for a in agents:
        by_status[a.status] = by_status.get(a.status, 0) + 1

    decision_counts = dict(
        db.execute(
            select(AuditEvent.decision, func.count()).where(AuditEvent.decision.is_not(None)).group_by(AuditEvent.decision)
        ).all()
    )

    recent_denials = (
        db.execute(
            select(AuditEvent)
            .where(AuditEvent.decision.in_(["DENY", "REQUIRE_APPROVAL"]))
            .order_by(AuditEvent.timestamp.desc())
            .limit(20)
        )
        .scalars()
        .all()
    )

    agent_names = {a.id: a.name for a in agents}

    pending_approvals = db.execute(
        select(func.count()).select_from(Approval).where(Approval.status == "pending")
    ).scalar_one()

    agent_activity = []
    for agent in agents:
        permission_count = db.execute(
            select(func.count()).select_from(AgentPermission).where(AgentPermission.agent_id == agent.id)
        ).scalar_one()
        counts = dict(
            db.execute(
                select(AuditEvent.decision, func.count())
                .where(AuditEvent.agent_id == agent.id, AuditEvent.decision.is_not(None))
                .group_by(AuditEvent.decision)
            ).all()
        )
        agent_activity.append(
            {
                "agent_id": agent.id,
                "agent_name": agent.name,
                "status": agent.status,
                "permission_count": permission_count,
                "allow_count": counts.get("ALLOW", 0),
                "deny_count": counts.get("DENY", 0),
                "require_approval_count": counts.get("REQUIRE_APPROVAL", 0),
            }
        )

    return {
        "agents_by_status": by_status,
        "decision_counts": decision_counts,
        "pending_approvals": pending_approvals,
        "agent_activity": agent_activity,
        "recent_denials": [
            {
                "id": e.id,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                "agent_name": agent_names.get(e.agent_id, e.agent_id),
                "event_type": e.event_type,
                "decision": e.decision,
                "reason": e.reason,
                "policy_evaluated": e.policy_evaluated,
            }
            for e in recent_denials
        ],
    }
