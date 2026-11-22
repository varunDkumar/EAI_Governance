import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Agent, AuditEvent
from db.session import get_db
from governance.audit import verify_chain

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/events")
def list_events(
    event_type: str | None = None,
    decision: str | None = None,
    agent_id: str | None = None,
    q: str | None = None,
    limit: int = 200,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    stmt = select(AuditEvent)
    if event_type:
        stmt = stmt.where(AuditEvent.event_type == event_type)
    if decision:
        stmt = stmt.where(AuditEvent.decision == decision)
    if agent_id:
        stmt = stmt.where(AuditEvent.agent_id == agent_id)
    if q:
        stmt = stmt.where(AuditEvent.reason.ilike(f"%{q}%"))
    stmt = stmt.order_by(AuditEvent.timestamp.desc()).limit(limit).offset(offset)
    events = db.execute(stmt).scalars().all()
    agents = {a.id: a.name for a in db.execute(select(Agent)).scalars()}
    return {"events": [_event_to_dict(e, agents) for e in events]}


@router.get("/verify")
def verify_audit_chain(db: Session = Depends(get_db)):
    ok = verify_chain(db)
    return {
        "intact": ok,
        "note": (
            "Hash chain recomputed and matches stored hashes — no historical row has been altered. "
            "This is tamper-evidence (it detects edits after the fact), not cryptographic immutability."
            if ok
            else "Hash chain mismatch detected — historical audit rows may have been altered."
        ),
    }


@router.get("/export")
def export_events(format: str = "json", db: Session = Depends(get_db)):
    if format not in ("json", "csv"):
        raise HTTPException(400, "format must be 'json' or 'csv'")
    events = db.execute(select(AuditEvent).order_by(AuditEvent.timestamp.asc())).scalars().all()
    agents = {a.id: a.name for a in db.execute(select(Agent)).scalars()}
    rows = [_event_to_dict(e, agents) for e in events]

    if format == "json":
        import json

        return StreamingResponse(
            io.StringIO(json.dumps(rows, indent=2)),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=audit_log.json"},
        )

    buffer = io.StringIO()
    if rows:
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    buffer.seek(0)
    return StreamingResponse(
        buffer, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=audit_log.csv"}
    )


def _event_to_dict(e: AuditEvent, agents: dict[str, str]) -> dict:
    return {
        "id": e.id,
        "timestamp": e.timestamp.isoformat() if e.timestamp else None,
        "agent_id": e.agent_id,
        "agent_name": agents.get(e.agent_id, e.agent_id or "—"),
        "session_id": e.session_id,
        "event_type": e.event_type,
        "resource_id": e.resource_id,
        "requested_action": e.requested_action,
        "policy_evaluated": e.policy_evaluated,
        "decision": e.decision,
        "reason": e.reason,
        "approval_ref": e.approval_ref,
        "hash": e.hash,
    }
