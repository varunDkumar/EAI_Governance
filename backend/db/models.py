import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .session import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String)
    file_path: Mapped[str] = mapped_column(String)
    file_hash: Mapped[str] = mapped_column(String, index=True)
    file_type: Mapped[str] = mapped_column(String)
    term: Mapped[str | None] = mapped_column(String, nullable=True)
    course: Mapped[str | None] = mapped_column(String, nullable=True)
    course_code: Mapped[str | None] = mapped_column(String, nullable=True)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending|indexed|error
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    classification_confidence: Mapped[float | None] = mapped_column(nullable=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    chunks: Mapped[list["DocumentChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    slide_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(Text)
    chroma_id: Mapped[str] = mapped_column(String, index=True)

    document: Mapped["Document"] = relationship(back_populates="chunks")


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    slug: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text)
    purpose: Mapped[str] = mapped_column(Text)
    owner: Mapped[str] = mapped_column(String)
    permitted_tools: Mapped[list] = mapped_column(JSON, default=list)
    restricted_actions: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String, default="active")  # active|suspended|deactivated
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    permissions: Mapped[list["AgentPermission"]] = relationship(back_populates="agent", cascade="all, delete-orphan")


class AgentPermission(Base):
    __tablename__ = "agent_permissions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), index=True)
    resource_type: Mapped[str] = mapped_column(String)  # category|memory_type|tool
    resource_value: Mapped[str] = mapped_column(String)
    access_level: Mapped[str] = mapped_column(String, default="read")  # read|write

    agent: Mapped["Agent"] = relationship(back_populates="permissions")


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String)
    resource_type: Mapped[str] = mapped_column(String)  # document|memory|tool
    condition: Mapped[dict] = mapped_column(JSON, default=dict)
    effect: Mapped[str] = mapped_column(String)  # ALLOW|DENY|REQUIRE_APPROVAL
    reason: Mapped[str] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, default=100)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), index=True)
    title: Mapped[str] = mapped_column(String, default="New conversation")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String)  # user|assistant
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[list] = mapped_column(JSON, default=list)
    memories_used: Mapped[list] = mapped_column(JSON, default=list)
    governance_notes: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


class Memory(Base):
    __tablename__ = "memories"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    memory_type: Mapped[str] = mapped_column(String)  # knowledge|episodic|user_context|decision
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text)
    topic: Mapped[str | None] = mapped_column(String, nullable=True)
    agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id"), nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(ForeignKey("conversations.id"), nullable=True)
    supporting_documents: Mapped[list] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(default=0.7)
    access_permissions: Mapped[list] = mapped_column(JSON, default=list)
    approval_status: Mapped[str] = mapped_column(String, default="pending")  # pending|approved|rejected
    chroma_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    sources: Mapped[list["MemorySource"]] = relationship(back_populates="memory", cascade="all, delete-orphan")


class MemorySource(Base):
    __tablename__ = "memory_sources"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    memory_id: Mapped[str] = mapped_column(ForeignKey("memories.id"), index=True)
    source_type: Mapped[str] = mapped_column(String)  # document|conversation
    source_id: Mapped[str] = mapped_column(String)

    memory: Mapped["Memory"] = relationship(back_populates="sources")


class GraphNode(Base):
    __tablename__ = "graph_nodes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    node_type: Mapped[str] = mapped_column(String, index=True)
    label: Mapped[str] = mapped_column(String)
    properties: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class GraphEdge(Base):
    __tablename__ = "graph_edges"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    source_id: Mapped[str] = mapped_column(ForeignKey("graph_nodes.id"), index=True)
    target_id: Mapped[str] = mapped_column(ForeignKey("graph_nodes.id"), index=True)
    relation: Mapped[str] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(default=1.0)
    provenance: Mapped[str] = mapped_column(String, default="inferred")  # inferred|confirmed
    source_ref: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class SimulatorComparison(Base):
    """One paired, deterministic Governance Simulator demonstration."""

    __tablename__ = "simulator_comparisons"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    scenario_id: Mapped[str] = mapped_column(String, index=True)
    scenario_name: Mapped[str] = mapped_column(String)
    agent_id: Mapped[str] = mapped_column(String, default="patient-inbox-agent")
    agent_name: Mapped[str] = mapped_column(String, default="Patient Inbox Agent")
    model_label: Mapped[str] = mapped_column(String, default="Deterministic demo fixture")
    demo_mode: Mapped[bool] = mapped_column(Boolean, default=True)
    initial_input: Mapped[str] = mapped_column(Text)
    final_decision: Mapped[str] = mapped_column(String)
    approval_status: Mapped[str] = mapped_column(String, default="not_required")
    baseline_execution_id: Mapped[str] = mapped_column(String)
    governed_execution_id: Mapped[str] = mapped_column(String)
    principles_triggered: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class SimulatorExecution(Base):
    """Persisted output for one side of a simulator comparison."""

    __tablename__ = "simulator_executions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    comparison_id: Mapped[str] = mapped_column(ForeignKey("simulator_comparisons.id"), index=True)
    execution_mode: Mapped[str] = mapped_column(String)  # baseline|governed
    status: Mapped[str] = mapped_column(String)
    initial_input: Mapped[str] = mapped_column(Text)
    initial_context: Mapped[dict] = mapped_column(JSON, default=dict)
    initial_output: Mapped[str] = mapped_column(Text)
    final_output: Mapped[str] = mapped_column(Text)
    cne_results: Mapped[list] = mapped_column(JSON, default=list)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    correction_instruction: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision: Mapped[str] = mapped_column(String)
    deliverable: Mapped[bool] = mapped_column(Boolean, default=False)
    access_attempts: Mapped[list] = mapped_column(JSON, default=list)
    timeline: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class SimulatorApproval(Base):
    """Human-oversight decision for a simulated response; never sends it."""

    __tablename__ = "simulator_approvals"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    comparison_id: Mapped[str] = mapped_column(ForeignKey("simulator_comparisons.id"), index=True)
    scenario_id: Mapped[str] = mapped_column(String)
    agent_name: Mapped[str] = mapped_column(String)
    initial_output: Mapped[str] = mapped_column(Text)
    corrected_output: Mapped[str] = mapped_column(Text)
    findings: Mapped[list] = mapped_column(JSON, default=list)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String, default="pending")
    decided_by: Mapped[str | None] = mapped_column(String, nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"))
    action: Mapped[str] = mapped_column(String)
    resource_type: Mapped[str] = mapped_column(String)
    resource_id: Mapped[str | None] = mapped_column(String, nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    policy_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending|approved|rejected
    decided_by: Mapped[str | None] = mapped_column(String, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    agent_id: Mapped[str | None] = mapped_column(String, nullable=True)
    session_id: Mapped[str | None] = mapped_column(String, nullable=True)
    user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    event_type: Mapped[str] = mapped_column(String, index=True)
    resource_id: Mapped[str | None] = mapped_column(String, nullable=True)
    requested_action: Mapped[str | None] = mapped_column(String, nullable=True)
    policy_evaluated: Mapped[str | None] = mapped_column(String, nullable=True)
    decision: Mapped[str | None] = mapped_column(String, nullable=True)  # ALLOW|DENY|REQUIRE_APPROVAL
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    prev_hash: Mapped[str] = mapped_column(String, default="")
    hash: Mapped[str] = mapped_column(String, default="")


class AppSession(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    kind: Mapped[str] = mapped_column(String, default="app")  # app|agent
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# --- Governance Simulator v2: Apollo Hospital / CNE patient journey -------
# A synthetic, deterministic hospital scenario demonstrating the CNE
# (Coherence, Narrative Continuity, Exclusivity) protocol. Entirely separate
# from the academic Memory Intelligence data above; see PRODUCT.md.


class CnePatient(Base):
    __tablename__ = "cne_patients"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    patient_code: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String)
    age: Mapped[int] = mapped_column(Integer)
    gender: Mapped[str] = mapped_column(String)
    blood_group: Mapped[str] = mapped_column(String)
    registered_date: Mapped[str] = mapped_column(String)
    medical_history: Mapped[list] = mapped_column(JSON, default=list)
    medications: Mapped[list] = mapped_column(JSON, default=list)


class CneEpisode(Base):
    __tablename__ = "cne_episodes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    patient_id: Mapped[str] = mapped_column(ForeignKey("cne_patients.id"), index=True)
    name: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="open")  # open|closed
    opened_at: Mapped[str] = mapped_column(String)
    closed_at: Mapped[str | None] = mapped_column(String, nullable=True)


class CneEncounter(Base):
    """One hospital visit."""

    __tablename__ = "cne_encounters"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    episode_id: Mapped[str] = mapped_column(ForeignKey("cne_episodes.id"), index=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("cne_patients.id"), index=True)
    encounter_code: Mapped[str] = mapped_column(String, unique=True, index=True)
    visit_date: Mapped[str] = mapped_column(String)
    department: Mapped[str] = mapped_column(String)
    doctor_name: Mapped[str] = mapped_column(String)
    chief_complaint: Mapped[str] = mapped_column(Text)
    sequence: Mapped[int] = mapped_column(Integer, default=0)


class CneAgent(Base):
    """A CNE-identified AI agent: identity = H(Substrate Anchor || CoF-ID || Policy Set)."""

    __tablename__ = "cne_agents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String)
    cof_id: Mapped[str] = mapped_column(String, index=True)
    substrate_anchor: Mapped[str] = mapped_column(String)
    policy_set: Mapped[dict] = mapped_column(JSON, default=dict)
    cne_id: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, default="LIVE")  # LIVE|SUSPENDED|REJECTED
    narrative_seq: Mapped[int] = mapped_column(Integer, default=0)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class CneAction(Base):
    """One AI-generated workflow-stage output, for one scenario variant."""

    __tablename__ = "cne_actions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    encounter_id: Mapped[str] = mapped_column(ForeignKey("cne_encounters.id"), index=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("cne_agents.id"), index=True)
    scenario: Mapped[str] = mapped_column(String, index=True)  # without_cne|with_cne
    stage: Mapped[str] = mapped_column(String)
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    input_refs: Mapped[list] = mapped_column(JSON, default=list)
    output_text: Mapped[str] = mapped_column(Text)
    consumed_by: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending|accepted|modified|rejected
    cne_id_snapshot: Mapped[str | None] = mapped_column(String, nullable=True)
    gnf_frame_id: Mapped[str | None] = mapped_column(ForeignKey("cne_gnf_frames.id"), nullable=True)
    rbr_proof_id: Mapped[str | None] = mapped_column(ForeignKey("cne_rbr_proofs.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class CneGnfFrame(Base):
    """Global Narrative Frame: one hash-chained entry in an agent's narrative history."""

    __tablename__ = "cne_gnf_frames"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    agent_id: Mapped[str] = mapped_column(ForeignKey("cne_agents.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    prev_frame_hash: Mapped[str] = mapped_column(String)
    frame_hash: Mapped[str] = mapped_column(String)
    encounter_id: Mapped[str | None] = mapped_column(ForeignKey("cne_encounters.id"), nullable=True)
    summary: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class CneRbrProof(Base):
    """Recursive Belief Revision proof capsule: evidence that a belief update is traceable."""

    __tablename__ = "cne_rbr_proofs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    agent_id: Mapped[str] = mapped_column(ForeignKey("cne_agents.id"), index=True)
    encounter_id: Mapped[str] = mapped_column(ForeignKey("cne_encounters.id"), index=True)
    pre_belief_hash: Mapped[str] = mapped_column(String)
    evidence_hash: Mapped[str] = mapped_column(String)
    revision_rule_hash: Mapped[str] = mapped_column(String)
    post_belief_hash: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="coherent")  # coherent|flagged
    summary: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class CneGovernanceEvent(Base):
    """One of the 7 interactive governance events, or a detected exception."""

    __tablename__ = "cne_governance_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    event_type: Mapped[str] = mapped_column(String, index=True)
    scenario: Mapped[str] = mapped_column(String)  # without_cne|with_cne
    encounter_id: Mapped[str | None] = mapped_column(ForeignKey("cne_encounters.id"), nullable=True)
    agent_id: Mapped[str | None] = mapped_column(ForeignKey("cne_agents.id"), nullable=True)
    severity: Mapped[str] = mapped_column(String, default="info")  # info|warning|blocked
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class CneApproval(Base):
    """A doctor's accept/modify/reject decision on one CneAction."""

    __tablename__ = "cne_approvals"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    action_id: Mapped[str] = mapped_column(ForeignKey("cne_actions.id"), index=True)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending|approved|rejected|modified
    decided_by: Mapped[str | None] = mapped_column(String, nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
