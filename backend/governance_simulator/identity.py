"""CNE identity primitives: CNE-ID generation, RbR proof capsules, Global
Narrative Frames (GNF), and per-CoF-ID exclusivity enforcement.

All hashes are real SHA-256 over illustrative JSON payloads — the identity
math is genuine, the underlying clinical content is synthetic. See
PRODUCT.md and spec §5/§6/§12.15.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import CneAgent, CneGnfFrame, CneRbrProof

from .cne import canonical_hash

GNF_GENESIS = "CNE-GNF-GENESIS-v1"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def compute_cne_id(substrate_anchor: str, cof_id: str, policy_set: dict) -> str:
    """CNE-ID = H(Substrate Anchor || CoF-ID || Policy Set)."""
    return canonical_hash({"substrate_anchor": substrate_anchor, "cof_id": cof_id, "policy_set": policy_set})


def append_gnf_frame(db: Session, agent: CneAgent, *, encounter_id: str | None, summary: str, payload: dict) -> CneGnfFrame:
    """Append the next hash-chained narrative frame for this agent."""
    last = (
        db.execute(
            select(CneGnfFrame).where(CneGnfFrame.agent_id == agent.id).order_by(CneGnfFrame.seq.desc()).limit(1)
        )
        .scalars()
        .first()
    )
    prev_hash = last.frame_hash if last else GNF_GENESIS
    seq = agent.narrative_seq + 1
    body = {
        "agent_id": agent.id,
        "cne_id": agent.cne_id,
        "seq": seq,
        "prev_frame_hash": prev_hash,
        "encounter_id": encounter_id,
        "summary": summary,
        "payload": payload,
        "timestamp": now_iso(),
    }
    frame = CneGnfFrame(
        id=str(uuid4()),
        agent_id=agent.id,
        seq=seq,
        prev_frame_hash=prev_hash,
        frame_hash=canonical_hash(body),
        encounter_id=encounter_id,
        summary=summary,
        payload=payload,
    )
    db.add(frame)
    agent.narrative_seq = seq
    agent.last_activity_at = datetime.now(timezone.utc)
    db.flush()
    return frame


def verify_gnf_chain(frames: list[CneGnfFrame]) -> dict:
    """Check that each frame's prev_frame_hash correctly links to the one before it."""
    prev = GNF_GENESIS
    for index, frame in enumerate(frames):
        if frame.prev_frame_hash != prev:
            return {"valid": False, "failed_index": index, "failed_frame": frame.id}
        prev = frame.frame_hash
    return {"valid": True, "failed_index": None, "failed_frame": None}


def make_rbr_proof(
    db: Session,
    agent: CneAgent,
    *,
    encounter_id: str,
    pre_belief: dict,
    evidence: dict,
    revision_rule: str,
    post_belief: dict,
    summary: str,
) -> CneRbrProof:
    """Record a Recursive Belief Revision proof capsule for one evidence-driven update."""
    proof = CneRbrProof(
        id=str(uuid4()),
        agent_id=agent.id,
        encounter_id=encounter_id,
        pre_belief_hash=canonical_hash(pre_belief),
        evidence_hash=canonical_hash(evidence),
        revision_rule_hash=canonical_hash({"rule": revision_rule}),
        post_belief_hash=canonical_hash(post_belief),
        status="coherent",
        summary=summary,
    )
    db.add(proof)
    db.flush()
    return proof


def check_exclusivity(db: Session, cof_id: str, candidate_substrate_anchor: str) -> dict:
    """Is `candidate_substrate_anchor` the authorised LIVE head for this CoF-ID?

    Exclusivity is enforced per CoF-ID across substrates, not per patient or
    per visit (spec §6C) — this looks across every CneAgent row sharing the
    CoF-ID, regardless of which encounter is being processed.
    """
    agents = db.execute(select(CneAgent).where(CneAgent.cof_id == cof_id)).scalars().all()
    live = next((a for a in agents if a.status == "LIVE"), None)
    if live is None:
        return {"status": "pass", "live_agent_id": None, "finding": f"No LIVE agent yet registered for {cof_id}; first claim accepted."}
    if live.substrate_anchor == candidate_substrate_anchor:
        return {"status": "pass", "live_agent_id": live.id, "finding": f"Candidate substrate matches the LIVE agent for {cof_id}."}
    return {
        "status": "rejected",
        "live_agent_id": live.id,
        "finding": f"A LIVE agent already holds {cof_id} on substrate {live.substrate_anchor}; candidate on {candidate_substrate_anchor} cannot claim a second narrative head.",
    }
