"""Governance Simulator API: Apollo Hospital / CNE patient-journey demo.

Entirely synthetic and deterministic — see PRODUCT.md. This replaces the
earlier 3-scenario "Riverside" demo; see governance_simulator/journey_engine.py.
"""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import (
    CneAction,
    CneAgent,
    CneApproval,
    CneEncounter,
    CneEpisode,
    CneGnfFrame,
    CneGovernanceEvent,
    CnePatient,
    CneRbrProof,
)
from db.session import get_db
from governance_simulator import hospital_data
from governance_simulator.identity import append_gnf_frame, verify_gnf_chain
from governance_simulator.journey_engine import EVENT_HANDLERS, ensure_seeded

router = APIRouter(prefix="/simulator", tags=["governance-simulator"])


def _plain(value):
    if isinstance(value, list):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if hasattr(value, "__table__"):
        return {c.name: _plain(getattr(value, c.name)) for c in value.__table__.columns}
    if isinstance(value, datetime):
        return value.isoformat()
    return value


class EventRequest(BaseModel):
    action_id: str | None = None
    doctor_name: str | None = None


class ActionDecisionRequest(BaseModel):
    decision: str  # accepted|modified|rejected
    decided_by: str
    note: str | None = None
    edited_output: str | None = None


class ReconstructRequest(BaseModel):
    encounter_id: str | None = None
    agent_id: str | None = None
    action_id: str | None = None


@router.get("/hospital-overview")
def hospital_overview(db: Session = Depends(get_db)):
    ensure_seeded(db)
    patient = db.execute(select(CnePatient)).scalars().first()
    agents = db.execute(select(CneAgent)).scalars().all()
    actions = db.execute(select(CneAction)).scalars().all()
    frames = db.execute(select(CneGnfFrame)).scalars().all()
    proofs = db.execute(select(CneRbrProof)).scalars().all()
    events = db.execute(select(CneGovernanceEvent)).scalars().all()

    with_cne_actions = [a for a in actions if a.scenario == "with_cne"]
    metrics = {
        "total_ai_actions": len(with_cne_actions),
        "actions_with_verifiable_identity": sum(1 for a in with_cne_actions if a.cne_id_snapshot),
        "outputs_with_complete_provenance": sum(1 for a in with_cne_actions if a.gnf_frame_id),
        "human_consumption_events": sum(1 for a in with_cne_actions if a.status != "pending" and a.consumed_by),
        "coherence_checks_coherent": sum(1 for p in proofs if p.status == "coherent"),
        "coherence_checks_flagged": sum(1 for p in proofs if p.status == "flagged"),
        "narrative_frames_linked": len(frames),
        "duplicate_identity_attempts_detected": sum(1 for e in events if e.event_type == "duplicate_agent" and e.scenario == "with_cne" and e.severity == "blocked"),
        "patient_context_mismatches_detected": sum(1 for e in events if e.event_type == "cross_context_contamination" and e.scenario == "with_cne" and e.severity == "blocked"),
        "unresolved_governance_gaps": sum(1 for e in events if e.scenario == "without_cne" and e.severity in ("warning", "blocked")),
    }
    return {
        "hospital": hospital_data.HOSPITAL,
        "patient": _plain(patient),
        "agents": [_plain(a) for a in agents],
        "metrics": metrics,
    }


@router.get("/patient-journey")
def patient_journey(db: Session = Depends(get_db)):
    ensure_seeded(db)
    patient = db.execute(select(CnePatient)).scalars().first()
    episodes = db.execute(select(CneEpisode).where(CneEpisode.patient_id == patient.id)).scalars().all()
    agents_by_id = {a.id: a for a in db.execute(select(CneAgent)).scalars().all()}

    episode_payload = []
    for episode in episodes:
        encounters = db.execute(
            select(CneEncounter).where(CneEncounter.episode_id == episode.id).order_by(CneEncounter.sequence)
        ).scalars().all()
        encounter_payload = []
        for encounter in encounters:
            actions = db.execute(
                select(CneAction).where(CneAction.encounter_id == encounter.id).order_by(CneAction.sequence)
            ).scalars().all()
            by_scenario = {"without_cne": [], "with_cne": []}
            for action in actions:
                row = _plain(action)
                row["agent_name"] = agents_by_id[action.agent_id].name if action.agent_id in agents_by_id else None
                by_scenario[action.scenario].append(row)
            encounter_payload.append({**_plain(encounter), "actions": by_scenario})
        episode_payload.append({**_plain(episode), "encounters": encounter_payload})

    return {"patient": _plain(patient), "episodes": episode_payload}


@router.get("/agents")
def agents(db: Session = Depends(get_db)):
    ensure_seeded(db)
    rows = db.execute(select(CneAgent).order_by(CneAgent.created_at)).scalars().all()
    spec_by_cof = {a["cof_id"]: a for a in hospital_data.AGENTS}
    out = []
    for row in rows:
        payload = _plain(row)
        spec = spec_by_cof.get(row.cof_id)
        payload["responsibility"] = spec["responsibility"] if spec else None
        payload["substrate_label"] = spec["substrate_label"] if spec else None
        payload["runtime"] = spec["runtime"] if spec else None
        out.append(payload)
    return out


@router.get("/comparison")
def comparison(db: Session = Depends(get_db)):
    ensure_seeded(db)
    frames = db.execute(select(CneGnfFrame)).scalars().all()
    proofs = db.execute(select(CneRbrProof)).scalars().all()
    agents_rows = db.execute(select(CneAgent)).scalars().all()
    actions = db.execute(select(CneAction).where(CneAction.scenario == "with_cne")).scalars().all()
    duplicate_blocked = db.execute(
        select(CneGovernanceEvent).where(CneGovernanceEvent.event_type == "duplicate_agent", CneGovernanceEvent.severity == "blocked")
    ).scalars().all()

    dimensions = [
        {"dimension": "Agent identity", "without_cne": "Conventional service identity", "with_cne": f"Verifiable CNE-ID ({len(agents_rows)} agents registered)"},
        {"dimension": "Hardware binding", "without_cne": "No CNE substrate binding", "with_cne": "Substrate Anchor per agent"},
        {"dimension": "Agent purpose", "without_cne": "Application-defined role", "with_cne": "CoF-ID per agent"},
        {"dimension": "Policy enforcement", "without_cne": "Existing application controls", "with_cne": "Bound CNE Policy Set (department / task / patient)"},
        {"dimension": "Reasoning coherence", "without_cne": "No CNE-based proof chain", "with_cne": f"RbR Proof Capsule ({len(proofs)} recorded)"},
        {"dimension": "Narrative continuity", "without_cne": "Fragmented agent-level history", "with_cne": f"Linked GNF frames ({len(frames)} recorded)"},
        {"dimension": "Duplicate agents", "without_cne": "No CNE exclusivity guarantee", "with_cne": f"One LIVE head per CoF-ID ({len(duplicate_blocked)} duplicate(s) rejected)"},
        {"dimension": "Output provenance", "without_cne": "Fragmented records", "with_cne": f"Attributable action receipts ({sum(1 for a in actions if a.cne_id_snapshot)})"},
        {"dimension": "Human consumption", "without_cne": "Conventional application logs", "with_cne": "Agent-to-human action linkage"},
        {"dimension": "Auditability", "without_cne": "Manual reconstruction", "with_cne": "Verifiable identity and event trail"},
        {"dimension": "Cross-context governance", "without_cne": "Existing access controls", "with_cne": "Patient/encounter references plus policy enforcement"},
    ]
    return {"dimensions": dimensions}


@router.post("/events/{event_type}")
def trigger_event(event_type: str, request: EventRequest, db: Session = Depends(get_db)):
    ensure_seeded(db)
    handler = EVENT_HANDLERS.get(event_type)
    if handler is None:
        raise HTTPException(404, f"Unknown event type: {event_type}")
    payload = request.model_dump(exclude_none=True)
    return handler(db, payload)


@router.post("/actions/{action_id}/decision")
def decide_action(action_id: str, request: ActionDecisionRequest, db: Session = Depends(get_db)):
    if request.decision not in {"accepted", "modified", "rejected"}:
        raise HTTPException(422, "decision must be accepted, modified or rejected")
    action = db.get(CneAction, action_id)
    if action is None:
        raise HTTPException(404, "Action not found")
    action.status = request.decision
    action.consumed_by = request.decided_by
    if request.edited_output and request.decision == "modified":
        action.output_text = request.edited_output
    approval = CneApproval(
        id=str(uuid4()), action_id=action.id, status=request.decision,
        decided_by=request.decided_by, decision_note=request.note, decided_at=datetime.now(timezone.utc),
    )
    db.add(approval)
    gnf_frame_seq = None
    if action.scenario == "with_cne":
        agent = db.get(CneAgent, action.agent_id)
        frame = append_gnf_frame(
            db, agent, encounter_id=action.encounter_id,
            summary=f"{request.decided_by} marked this action's output {request.decision}.",
            payload={"action_id": action.id, "decision": request.decision},
        )
        gnf_frame_seq = frame.seq
    db.commit()
    db.refresh(action)
    return {"action": _plain(action), "approval": _plain(approval), "gnf_frame_seq": gnf_frame_seq}


@router.get("/audit")
def audit(db: Session = Depends(get_db)):
    ensure_seeded(db)
    agents_rows = db.execute(select(CneAgent)).scalars().all()
    chains = []
    for agent in agents_rows:
        frames = db.execute(select(CneGnfFrame).where(CneGnfFrame.agent_id == agent.id).order_by(CneGnfFrame.seq)).scalars().all()
        chains.append({
            "agent_id": agent.id, "agent_name": agent.name, "cof_id": agent.cof_id,
            "frame_count": len(frames), "verification": verify_gnf_chain(frames),
        })
    events = db.execute(select(CneGovernanceEvent).order_by(CneGovernanceEvent.created_at.desc()).limit(200)).scalars().all()
    return {"chains": chains, "events": [_plain(e) for e in events]}


@router.post("/audit/reconstruct")
def reconstruct(request: ReconstructRequest, db: Session = Depends(get_db)):
    """Spec §10: 'Reconstruct Complete AI Decision Trail'."""
    ensure_seeded(db)
    stmt = select(CneAction)
    if request.action_id:
        stmt = stmt.where(CneAction.id == request.action_id)
    elif request.encounter_id:
        stmt = stmt.where(CneAction.encounter_id == request.encounter_id)
    elif request.agent_id:
        stmt = stmt.where(CneAction.agent_id == request.agent_id)
    else:
        raise HTTPException(422, "Provide encounter_id, agent_id or action_id")
    actions = db.execute(stmt.order_by(CneAction.sequence)).scalars().all()
    if not actions:
        raise HTTPException(404, "No matching actions found")

    trail = []
    for action in actions:
        agent = db.get(CneAgent, action.agent_id)
        encounter = db.get(CneEncounter, action.encounter_id)
        entry = {
            "action": _plain(action),
            "agent": _plain(agent) if agent else None,
            "encounter": _plain(encounter) if encounter else None,
        }
        if action.scenario == "with_cne":
            if action.gnf_frame_id:
                entry["gnf_frame"] = _plain(db.get(CneGnfFrame, action.gnf_frame_id))
            if action.rbr_proof_id:
                entry["rbr_proof"] = _plain(db.get(CneRbrProof, action.rbr_proof_id))
            entry["approvals"] = [_plain(a) for a in db.execute(select(CneApproval).where(CneApproval.action_id == action.id)).scalars().all()]
        trail.append(entry)
    return {"trail": trail}
