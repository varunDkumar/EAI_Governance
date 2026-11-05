"""Seeds the Apollo Hospital / Rajesh Kumar patient journey and implements
the 7 interactive governance events (spec §8).

Design: the "without CNE" universe has no real identity/continuity/
exclusivity mechanism, so its side of every event is *descriptive* (a
CneGovernanceEvent explaining what's missing) rather than a system that
actually enforces anything. The "with CNE" universe does real work:
computed CNE-IDs, real RbR proof capsules, a real hash-chained GNF per
agent, and a real per-CoF-ID exclusivity check — see identity.py.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import (
    CneAction,
    CneAgent,
    CneEncounter,
    CneEpisode,
    CneGovernanceEvent,
    CnePatient,
)

from . import hospital_data as data
from .identity import append_gnf_frame, check_exclusivity, compute_cne_id, make_rbr_proof

SCENARIOS = ("without_cne", "with_cne")


def _log_event(db: Session, event_type: str, scenario: str, *, encounter_id: str | None = None, agent_id: str | None = None, severity: str = "info", detail: dict | None = None) -> CneGovernanceEvent:
    event = CneGovernanceEvent(
        id=str(uuid4()), event_type=event_type, scenario=scenario,
        encounter_id=encounter_id, agent_id=agent_id, severity=severity, detail=detail or {},
    )
    db.add(event)
    db.flush()
    return event


def ensure_seeded(db: Session) -> None:
    """Idempotently seed the hospital, patient, episodes, encounters, agents and
    the full patient-journey action history for both scenarios."""
    if db.execute(select(CnePatient).limit(1)).scalars().first() is not None:
        return

    patient = CnePatient(id=str(uuid4()), **data.PATIENT)
    db.add(patient)
    db.flush()

    episodes: dict[str, CneEpisode] = {}
    for ep in data.EPISODES:
        row = CneEpisode(
            id=str(uuid4()), patient_id=patient.id, name=ep["name"],
            status=ep["status"], opened_at=ep["opened_at"], closed_at=ep["closed_at"],
        )
        db.add(row)
        episodes[ep["key"]] = row
    db.flush()

    agents: dict[str, CneAgent] = {}
    for a in data.AGENTS:
        cne_id = compute_cne_id(a["substrate_anchor"], a["cof_id"], a["policy_set"])
        row = CneAgent(
            id=str(uuid4()), name=a["name"], cof_id=a["cof_id"],
            substrate_anchor=a["substrate_anchor"], policy_set=a["policy_set"],
            cne_id=cne_id, status="LIVE", narrative_seq=0,
        )
        db.add(row)
        agents[a["key"]] = row
    db.flush()

    for index, enc in enumerate(data.ENCOUNTERS):
        episode = episodes[enc["episode"]]
        encounter = CneEncounter(
            id=str(uuid4()), episode_id=episode.id, patient_id=patient.id,
            encounter_code=enc["encounter_code"], visit_date=enc["visit_date"],
            department=enc["department"], doctor_name=enc["doctor_name"],
            chief_complaint=enc["chief_complaint"], sequence=index,
        )
        db.add(encounter)
        db.flush()

        for stage_index, stage in enumerate(enc["stages"]):
            agent = agents[stage["agent"]]
            _run_stage(db, encounter, agent, stage, stage_index)

    db.commit()


def _run_stage(db: Session, encounter: CneEncounter, agent: CneAgent, stage: dict, sequence: int) -> None:
    # Without CNE: the output exists, but nothing establishes a verifiable
    # agent identity, provenance link or narrative continuity for it.
    db.add(CneAction(
        id=str(uuid4()), encounter_id=encounter.id, agent_id=agent.id, scenario="without_cne",
        stage=stage["stage"], sequence=sequence, input_refs=stage["input_refs"],
        output_text=stage["output"], consumed_by=stage["consumed_by"], status="pending",
        cne_id_snapshot=None, gnf_frame_id=None, rbr_proof_id=None,
    ))

    # With CNE: the same output, now carrying a verified identity and a
    # narrative frame; coherence-relevant stages also get an RbR proof.
    rbr_id = None
    if stage.get("coherence"):
        proof = make_rbr_proof(
            db, agent, encounter_id=encounter.id,
            pre_belief={"encounter": encounter.encounter_code, "stage": stage["stage"], "state": "pre"},
            evidence={"input_refs": stage["input_refs"]},
            revision_rule=f"{stage['stage']}-evidence-update",
            post_belief={"encounter": encounter.encounter_code, "stage": stage["stage"], "output": stage["output"]},
            summary=f"{agent.name} revised its assessment for {encounter.encounter_code} ({stage['stage']}) from the cited evidence.",
        )
        rbr_id = proof.id

    frame = append_gnf_frame(
        db, agent, encounter_id=encounter.id,
        summary=f"{stage['stage']} for {encounter.encounter_code}: {stage['output'][:96]}",
        payload={"stage": stage["stage"], "encounter": encounter.encounter_code, "input_refs": stage["input_refs"]},
    )

    db.add(CneAction(
        id=str(uuid4()), encounter_id=encounter.id, agent_id=agent.id, scenario="with_cne",
        stage=stage["stage"], sequence=sequence, input_refs=stage["input_refs"],
        output_text=stage["output"], consumed_by=stage["consumed_by"], status="pending",
        cne_id_snapshot=agent.cne_id, gnf_frame_id=frame.id, rbr_proof_id=rbr_id,
    ))


# --- The 7 interactive governance events (spec §8) --------------------------

def _agent(db: Session, key: str) -> CneAgent:
    cof_id = next(a["cof_id"] for a in data.AGENTS if a["key"] == key)
    return db.execute(select(CneAgent).where(CneAgent.cof_id == cof_id, CneAgent.status == "LIVE")).scalars().first()


def _encounter(db: Session, code: str) -> CneEncounter:
    return db.execute(select(CneEncounter).where(CneEncounter.encounter_code == code)).scalars().one()


def trigger_normal_consultation(db: Session) -> dict:
    encounter = _encounter(db, "ENC-0001")
    agent = _agent(db, "triage")
    _log_event(db, "normal_consultation", "without_cne", encounter_id=encounter.id, agent_id=agent.id, severity="info",
               detail={"finding": "Triage agent processed the request. The hospital can identify the application that generated it, but not a verifiable, persistent identity for this specific agent instance."})
    frame = append_gnf_frame(db, agent, encounter_id=encounter.id, summary="Re-ran patient-intake stage (event trigger).", payload={"event": "normal_consultation"})
    _log_event(db, "normal_consultation", "with_cne", encounter_id=encounter.id, agent_id=agent.id, severity="info",
               detail={"finding": "Agent identity verified via CNE-ID; action recorded as GNF frame.", "cne_id": agent.cne_id, "gnf_frame_seq": frame.seq})
    db.commit()
    return {"without_cne": {"identity_verified": False}, "with_cne": {"identity_verified": True, "gnf_frame_seq": frame.seq}}


def trigger_new_diagnostic_evidence(db: Session) -> dict:
    encounter = _encounter(db, "ENC-0002")
    agent = _agent(db, "diagnostic")
    _log_event(db, "new_diagnostic_evidence", "without_cne", encounter_id=encounter.id, agent_id=agent.id, severity="warning",
               detail={"finding": "New lab report updates the diagnosis, but the reasoning chain linking the old assessment, the new evidence and the revised conclusion is not reliably preserved."})
    proof = make_rbr_proof(
        db, agent, encounter_id=encounter.id,
        pre_belief={"assessment": "uncomplicated lower respiratory tract infection"},
        evidence={"new_report": "repeat CRP 6 mg/L, chest X-ray resolved"},
        revision_rule="evidence-contradicts-or-confirms-prior-belief",
        post_belief={"assessment": "resolving infection, post-infective cough"},
        summary="New CRP/X-ray evidence formally revises the 05 Nov assessment.",
    )
    frame = append_gnf_frame(db, agent, encounter_id=encounter.id, summary="Recorded RbR proof for new diagnostic evidence.", payload={"rbr_proof_id": proof.id})
    _log_event(db, "new_diagnostic_evidence", "with_cne", encounter_id=encounter.id, agent_id=agent.id, severity="info",
               detail={"finding": "RbR proof capsule recorded: pre-belief, evidence and post-belief hashes are all linked.", "rbr_proof_id": proof.id, "gnf_frame_seq": frame.seq})
    db.commit()
    return {"without_cne": {"proof_recorded": False}, "with_cne": {"proof_recorded": True, "rbr_proof_id": proof.id}}


def trigger_duplicate_agent(db: Session) -> dict:
    original = _agent(db, "treatment")
    spec = next(a for a in data.AGENTS if a["key"] == "treatment")
    duplicate_substrate = "SA-HOSP-005-DUP"
    cne_id = compute_cne_id(duplicate_substrate, spec["cof_id"], spec["policy_set"])
    duplicate = CneAgent(
        id=str(uuid4()), name=spec["name"] + " (duplicate instance)", cof_id=spec["cof_id"],
        substrate_anchor=duplicate_substrate, policy_set=spec["policy_set"], cne_id=cne_id,
        status="PENDING", narrative_seq=0,
    )
    db.add(duplicate)
    db.flush()

    _log_event(db, "duplicate_agent", "without_cne", agent_id=duplicate.id, severity="warning",
               detail={"finding": f"A second Treatment Recommendation Agent instance appeared on {duplicate_substrate}. Both instances can generate recommendations under apparently similar service identities; there is no mechanism to determine which is the authoritative continuing identity."})

    result = check_exclusivity(db, spec["cof_id"], duplicate_substrate)
    duplicate.status = "REJECTED" if result["status"] == "rejected" else "LIVE"
    _log_event(db, "duplicate_agent", "with_cne", agent_id=duplicate.id, severity="blocked" if result["status"] == "rejected" else "info",
               detail={"finding": result["finding"], "cof_id": spec["cof_id"], "live_agent_id": result["live_agent_id"], "duplicate_status": duplicate.status})
    db.commit()
    return {"without_cne": {"both_allowed": True}, "with_cne": {"original_status": "LIVE", "duplicate_status": duplicate.status, "cof_id": spec["cof_id"]}}


def trigger_cross_context_contamination(db: Session) -> dict:
    source_encounter = _encounter(db, "ENC-0001")  # respiratory treatment recommendation
    target_encounter = _encounter(db, "ENC-0004")  # unrelated orthopaedic visit
    source_action = db.execute(
        select(CneAction).where(CneAction.encounter_id == source_encounter.id, CneAction.stage == "treatment", CneAction.scenario == "with_cne")
    ).scalars().first()

    _log_event(db, "cross_context_contamination", "without_cne", encounter_id=target_encounter.id, severity="warning",
               detail={"finding": "An agent attempting to retrieve context for the orthopaedic visit could surface the outdated respiratory treatment recommendation. The system can flag this as unusual, but has no identity-based exclusivity/continuity guarantee to block it or establish how it happened."})

    target_episode_id = target_encounter.episode_id
    source_episode_id = source_encounter.episode_id
    blocked = target_episode_id != source_episode_id
    _log_event(db, "cross_context_contamination", "with_cne", encounter_id=target_encounter.id, severity="blocked" if blocked else "info",
               detail={"finding": "Patient/encounter reference and episode-scoped policy check rejected the cross-episode retrieval." if blocked else "Same episode; retrieval permitted.",
                       "source_encounter": source_encounter.encounter_code, "target_encounter": target_encounter.encounter_code,
                       "source_action_id": source_action.id if source_action else None})
    db.commit()
    return {"without_cne": {"blocked": False}, "with_cne": {"blocked": blocked}}


def trigger_new_unrelated_treatment(db: Session) -> dict:
    respiratory_encounters = db.execute(
        select(CneEncounter).join(CneEpisode).where(CneEpisode.name == "Respiratory illness")
    ).scalars().all()
    orthopaedic_encounter = _encounter(db, "ENC-0004")
    _log_event(db, "new_unrelated_treatment", "without_cne", encounter_id=orthopaedic_encounter.id, severity="warning",
               detail={"finding": "The hospital can retrieve the patient's previous respiratory records, but agent-level continuity and context separation between episodes are not guaranteed by any CNE mechanism."})
    _log_event(db, "new_unrelated_treatment", "with_cne", encounter_id=orthopaedic_encounter.id, severity="info",
               detail={"finding": "Same Patient ID retained; new, separately-scoped encounter established. Orthopaedic actions reference only this encounter's GNF frames, not the respiratory episode's.",
                       "patient_code": data.PATIENT["patient_code"], "prior_encounters": [e.encounter_code for e in respiratory_encounters]})
    db.commit()
    return {"without_cne": {"episode_separation_guaranteed": False}, "with_cne": {"episode_separation_guaranteed": True, "prior_encounters": [e.encounter_code for e in respiratory_encounters]}}


def trigger_agent_substrate_change(db: Session) -> dict:
    agent = _agent(db, "diagnostic")
    old_substrate = agent.substrate_anchor
    spec = next(a for a in data.AGENTS if a["key"] == "diagnostic")
    new_substrate = old_substrate + "-R2"

    _log_event(db, "agent_substrate_change", "without_cne", agent_id=agent.id, severity="warning",
               detail={"finding": f"Diagnostic Agent restarted on {new_substrate}. Without a substrate-binding identity, this can be silently treated as the same unchanged agent, fragmenting its history across the move."})

    new_cne_id = compute_cne_id(new_substrate, spec["cof_id"], spec["policy_set"])
    old_cne_id = agent.cne_id
    frame = append_gnf_frame(db, agent, encounter_id=None, summary=f"Substrate re-anchor: {old_substrate} → {new_substrate}.", payload={"old_cne_id": old_cne_id, "new_cne_id": new_cne_id})
    agent.substrate_anchor = new_substrate
    agent.cne_id = new_cne_id
    _log_event(db, "agent_substrate_change", "with_cne", agent_id=agent.id, severity="info",
               detail={"finding": "Substrate change required re-anchoring; old and new CNE-IDs are both recorded and linked via a GNF frame, preserving continuity.",
                       "old_substrate": old_substrate, "new_substrate": new_substrate, "old_cne_id": old_cne_id, "new_cne_id": new_cne_id, "gnf_frame_seq": frame.seq})
    db.commit()
    return {"without_cne": {"transition_recorded": False}, "with_cne": {"transition_recorded": True, "old_cne_id": old_cne_id, "new_cne_id": new_cne_id}}


# "Doctor consumes AI output" (spec §8 Event 3) is handled by the dedicated
# POST /simulator/actions/{id}/decision endpoint instead of living here —
# it needs a specific action_id and doctor-facing accept/modify/reject
# semantics that don't fit this dispatch-by-name shape.
EVENT_HANDLERS = {
    "normal_consultation": lambda db, payload: trigger_normal_consultation(db),
    "new_diagnostic_evidence": lambda db, payload: trigger_new_diagnostic_evidence(db),
    "duplicate_agent": lambda db, payload: trigger_duplicate_agent(db),
    "cross_context_contamination": lambda db, payload: trigger_cross_context_contamination(db),
    "new_unrelated_treatment": lambda db, payload: trigger_new_unrelated_treatment(db),
    "agent_substrate_change": lambda db, payload: trigger_agent_substrate_change(db),
}
