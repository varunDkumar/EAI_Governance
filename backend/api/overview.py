from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models import Agent, Approval, AuditEvent, Document, GraphEdge, GraphNode, Memory
from db.session import get_db

router = APIRouter(prefix="/overview", tags=["overview"])


@router.get("")
def overview(db: Session = Depends(get_db)):
    total_documents = db.execute(select(func.count()).select_from(Document)).scalar_one()
    indexed_documents = db.execute(
        select(func.count()).select_from(Document).where(Document.status == "indexed")
    ).scalar_one()
    total_nodes = db.execute(select(func.count()).select_from(GraphNode)).scalar_one()
    total_edges = db.execute(select(func.count()).select_from(GraphEdge)).scalar_one()
    active_agents = db.execute(
        select(func.count()).select_from(Agent).where(Agent.status == "active")
    ).scalar_one()
    total_agents = db.execute(select(func.count()).select_from(Agent)).scalar_one()
    memories_stored = db.execute(
        select(func.count()).select_from(Memory).where(Memory.approval_status == "approved")
    ).scalar_one()
    pending_approvals = db.execute(
        select(func.count()).select_from(Approval).where(Approval.status == "pending")
    ).scalar_one()

    agents = {a.id: a.name for a in db.execute(select(Agent)).scalars()}
    recent_events = (
        db.execute(select(AuditEvent).order_by(AuditEvent.timestamp.desc()).limit(8)).scalars().all()
    )

    return {
        "documents": {"total": total_documents, "indexed": indexed_documents},
        "knowledge_graph": {"nodes": total_nodes, "edges": total_edges},
        "agents": {"active": active_agents, "total": total_agents},
        "memories_stored": memories_stored,
        "pending_approvals": pending_approvals,
        "recent_events": [
            {
                "id": e.id,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                "agent_name": agents.get(e.agent_id, e.agent_id or "—"),
                "event_type": e.event_type,
                "decision": e.decision,
                "reason": e.reason,
            }
            for e in recent_events
        ],
    }
