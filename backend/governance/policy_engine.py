from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Agent, AgentPermission, Document, Memory

from .audit import log_event

ALLOW = "ALLOW"
DENY = "DENY"
REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


@dataclass
class Decision:
    effect: str
    reason: str
    policy: str

    @property
    def allowed(self) -> bool:
        return self.effect == ALLOW


def _has_permission(db: Session, agent_id: str, resource_type: str, resource_value: str, access_level: str) -> bool:
    if not resource_value:
        return False
    stmt = select(AgentPermission).where(
        AgentPermission.agent_id == agent_id,
        AgentPermission.resource_type == resource_type,
        AgentPermission.resource_value == resource_value,
    )
    perms = db.execute(stmt).scalars().all()
    if access_level == "read":
        return len(perms) > 0
    return any(p.access_level == "write" for p in perms)


def evaluate_document_access(db: Session, agent: Agent, document: Document, *, session_id: str | None = None) -> Decision:
    """Backend-enforced governance check — never trusts the LLM to self-report
    an allowed action. Every call is audited regardless of outcome."""
    material_type = (document.tags or [None])[0]

    if agent.status != "active":
        decision = Decision(DENY, f"Agent '{agent.name}' is not active (status: {agent.status}).", "suspended-agent-block")
    elif _has_permission(db, agent.id, "material_type", material_type or "", "read") or _has_permission(
        db, agent.id, "category", document.category or "", "read"
    ):
        decision = Decision(
            ALLOW,
            f"Agent '{agent.name}' holds a permission covering '{material_type}' documents.",
            "collection-permission-granted",
        )
    else:
        decision = Decision(
            DENY,
            f"Agent '{agent.name}' has no permission covering material type '{material_type}' or category '{document.category}'.",
            "collection-permission-required",
        )

    log_event(
        db,
        event_type="document_access",
        agent_id=agent.id,
        session_id=session_id,
        resource_id=document.id,
        requested_action="read_document",
        policy_evaluated=decision.policy,
        decision=decision.effect,
        reason=decision.reason,
    )
    return decision


def evaluate_memory_read(db: Session, agent: Agent, memory: Memory, *, session_id: str | None = None) -> Decision:
    if agent.status != "active":
        decision = Decision(DENY, f"Agent '{agent.name}' is not active (status: {agent.status}).", "suspended-agent-block")
    elif _has_permission(db, agent.id, "memory_type", memory.memory_type, "read"):
        decision = Decision(
            ALLOW,
            f"Agent '{agent.name}' holds read access to '{memory.memory_type}' memories.",
            "memory-read-permission-granted",
        )
    else:
        decision = Decision(
            DENY,
            f"Agent '{agent.name}' has no read permission for '{memory.memory_type}' memories.",
            "memory-read-permission-required",
        )

    log_event(
        db,
        event_type="memory_access",
        agent_id=agent.id,
        session_id=session_id,
        resource_id=memory.id,
        requested_action="read_memory",
        policy_evaluated=decision.policy,
        decision=decision.effect,
        reason=decision.reason,
    )
    return decision


def evaluate_memory_write(
    db: Session,
    agent: Agent,
    memory_type: str,
    *,
    is_modification: bool = False,
    target_approval_status: str | None = None,
    session_id: str | None = None,
    resource_id: str | None = None,
) -> Decision:
    """Covers both new-memory proposals and edits to existing memories.
    Modifying an already-approved memory always requires human sign-off,
    regardless of the agent's standing write permission. So does writing a new
    `user_context` memory — the PRD singles out "persistent personal memories"
    as always needing approval, since they're the most sensitive memory type
    (a durable profile of the specific student). Other memory types (working
    knowledge, episodic logs, case-analysis decisions) can auto-save once an
    agent holds standing write permission for them."""
    if agent.status != "active":
        decision = Decision(DENY, f"Agent '{agent.name}' is not active (status: {agent.status}).", "suspended-agent-block")
    elif is_modification and target_approval_status == "approved":
        decision = Decision(
            REQUIRE_APPROVAL,
            f"Modifying an already-approved '{memory_type}' memory requires human approval.",
            "protected-memory-modification",
        )
    elif memory_type == "user_context" and not is_modification:
        decision = Decision(
            REQUIRE_APPROVAL,
            f"Agent '{agent.name}' proposed a persistent personal memory about the student; these always require human approval before being saved.",
            "personal-memory-requires-approval",
        )
    elif _has_permission(db, agent.id, "memory_type", memory_type, "write"):
        decision = Decision(
            ALLOW,
            f"Agent '{agent.name}' holds write access to '{memory_type}' memories.",
            "memory-write-permission-granted",
        )
    else:
        decision = Decision(
            REQUIRE_APPROVAL,
            f"Agent '{agent.name}' has no standing write permission for '{memory_type}' memories; proposing for human approval.",
            "memory-write-permission-required",
        )

    log_event(
        db,
        event_type="memory_write",
        agent_id=agent.id,
        session_id=session_id,
        resource_id=resource_id,
        requested_action="modify_memory" if is_modification else "create_memory",
        policy_evaluated=decision.policy,
        decision=decision.effect,
        reason=decision.reason,
    )
    return decision
