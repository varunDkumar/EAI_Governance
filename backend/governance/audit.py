import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import AuditEvent


def _hash_row(prev_hash: str, payload: dict) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(prev_hash.encode("utf-8") + blob).hexdigest()


def log_event(
    db: Session,
    *,
    event_type: str,
    agent_id: str | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
    resource_id: str | None = None,
    requested_action: str | None = None,
    policy_evaluated: str | None = None,
    decision: str | None = None,
    reason: str | None = None,
    approval_ref: str | None = None,
) -> AuditEvent:
    """Append-only, hash-chained audit event. Tamper-evident (detects edits to
    history), not a claim of cryptographic immutability."""
    last = db.execute(select(AuditEvent).order_by(AuditEvent.timestamp.desc()).limit(1)).scalar_one_or_none()
    prev_hash = last.hash if last else ""

    event = AuditEvent(
        event_type=event_type,
        agent_id=agent_id,
        session_id=session_id,
        user_id=user_id,
        resource_id=resource_id,
        requested_action=requested_action,
        policy_evaluated=policy_evaluated,
        decision=decision,
        reason=reason,
        approval_ref=approval_ref,
        prev_hash=prev_hash,
    )
    payload = {
        "event_type": event.event_type,
        "agent_id": event.agent_id,
        "resource_id": event.resource_id,
        "requested_action": event.requested_action,
        "decision": event.decision,
        "reason": event.reason,
    }
    event.hash = _hash_row(prev_hash, payload)

    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def verify_chain(db: Session) -> bool:
    """Recomputes the hash chain to detect tampering with historical rows."""
    events = db.execute(select(AuditEvent).order_by(AuditEvent.timestamp.asc())).scalars().all()
    prev_hash = ""
    for event in events:
        payload = {
            "event_type": event.event_type,
            "agent_id": event.agent_id,
            "resource_id": event.resource_id,
            "requested_action": event.requested_action,
            "decision": event.decision,
            "reason": event.reason,
        }
        if event.prev_hash != prev_hash or event.hash != _hash_row(prev_hash, payload):
            return False
        prev_hash = event.hash
    return True
