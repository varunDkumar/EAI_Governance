from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from datetime import datetime, timezone

from db.models import Approval, Memory, MemorySource
from db.session import get_db
from governance.audit import log_event
from memory.engine import index_memory, unindex_memory

router = APIRouter(prefix="/memories", tags=["memories"])


@router.get("")
def list_memories(
    memory_type: str | None = None,
    approval_status: str | None = None,
    agent_id: str | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
):
    stmt = select(Memory)
    if memory_type:
        stmt = stmt.where(Memory.memory_type == memory_type)
    if approval_status:
        stmt = stmt.where(Memory.approval_status == approval_status)
    if agent_id:
        stmt = stmt.where(Memory.agent_id == agent_id)
    if q:
        stmt = stmt.where(Memory.title.ilike(f"%{q}%"))
    stmt = stmt.order_by(Memory.created_at.desc())
    memories = db.execute(stmt).scalars().all()
    return {"memories": [_memory_to_dict(m) for m in memories]}


@router.get("/{memory_id}")
def get_memory(memory_id: str, db: Session = Depends(get_db)):
    memory = db.get(Memory, memory_id)
    if memory is None:
        raise HTTPException(404, "Memory not found")
    payload = _memory_to_dict(memory)
    payload["sources"] = [{"source_type": s.source_type, "source_id": s.source_id} for s in memory.sources]
    return payload


def _sync_pending_approval(db: Session, memory_id: str, status: str) -> None:
    """Keep the Approval queue consistent when a memory is decided directly
    from the Memory Explorer rather than via the Approval Centre."""
    approval = db.execute(
        select(Approval).where(
            Approval.resource_type == "memory", Approval.resource_id == memory_id, Approval.status == "pending"
        )
    ).scalar_one_or_none()
    if approval is not None:
        approval.status = status
        approval.decided_by = "user"
        approval.decided_at = datetime.now(timezone.utc)
        db.commit()


@router.post("/{memory_id}/approve")
def approve_memory(memory_id: str, db: Session = Depends(get_db)):
    memory = db.get(Memory, memory_id)
    if memory is None:
        raise HTTPException(404, "Memory not found")
    memory.approval_status = "approved"
    db.commit()
    _sync_pending_approval(db, memory_id, "approved")
    index_memory(memory)
    log_event(
        db,
        event_type="human_approval",
        agent_id=memory.agent_id,
        resource_id=memory.id,
        requested_action="create_memory",
        decision="ALLOW",
        reason=f"Human approved memory '{memory.title}'.",
    )
    return _memory_to_dict(memory)


@router.post("/{memory_id}/reject")
def reject_memory(memory_id: str, db: Session = Depends(get_db)):
    memory = db.get(Memory, memory_id)
    if memory is None:
        raise HTTPException(404, "Memory not found")
    memory.approval_status = "rejected"
    db.commit()
    _sync_pending_approval(db, memory_id, "rejected")
    unindex_memory(memory.id)
    log_event(
        db,
        event_type="human_rejection",
        agent_id=memory.agent_id,
        resource_id=memory.id,
        requested_action="create_memory",
        decision="DENY",
        reason=f"Human rejected memory '{memory.title}'.",
    )
    return _memory_to_dict(memory)


@router.delete("/{memory_id}")
def delete_memory(memory_id: str, db: Session = Depends(get_db)):
    memory = db.get(Memory, memory_id)
    if memory is None:
        raise HTTPException(404, "Memory not found")
    db.execute(select(MemorySource).where(MemorySource.memory_id == memory_id))
    db.delete(memory)
    db.commit()
    unindex_memory(memory_id)
    log_event(
        db,
        event_type="memory_deletion",
        agent_id=memory.agent_id,
        resource_id=memory_id,
        requested_action="delete_memory",
        decision="ALLOW",
        reason=f"Human deleted memory '{memory.title}'.",
    )
    return {"status": "deleted"}


def _memory_to_dict(m: Memory) -> dict:
    return {
        "id": m.id,
        "memory_type": m.memory_type,
        "title": m.title,
        "description": m.description,
        "topic": m.topic,
        "agent_id": m.agent_id,
        "conversation_id": m.conversation_id,
        "confidence": m.confidence,
        "approval_status": m.approval_status,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }
