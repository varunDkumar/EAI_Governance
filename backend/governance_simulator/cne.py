"""Deterministic local CNE checks, authority rules, and tamper-evident events."""
from __future__ import annotations
import hashlib, json
from datetime import datetime, timezone
from uuid import uuid4

AGENT_ID = "RIVERSIDE-CLINICAL-ASSISTANT-001"
GENESIS = "CNE-GENESIS-v1"
DEFAULT_AGENT = {"agent_id": AGENT_ID, "logical_identity": "Riverside Clinical Assistant", "model_version": "2.1", "policy_version": "CLINICAL-SAFETY-004", "identity_status": "ACTIVE", "deployment_status": "AUTHORISED", "permissions": ["DRAFT_GENERATION", "RISK_FLAGGING"], "send_permission": False, "previous_version": "1.7", "version_history": []}
ROLE_PERMISSIONS = {"AI Agent": {"generate", "flag"}, "Nurse / Clinician": {"review", "edit", "approve", "reject", "escalate"}, "Senior Clinician / Supervisor": {"review", "edit", "approve", "reject", "escalate", "inspect"}, "Administrator": {"registry"}}

def now(): return datetime.now(timezone.utc).isoformat()
def canonical_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()

def make_event(interaction_id: str, event_type: str, outcome: str, evidence: str, previous_hash: str, policy_version="CLINICAL-SAFETY-004"):
    event = {"event_id": str(uuid4()), "interaction_id": interaction_id, "agent_id": AGENT_ID, "event_type": event_type, "timestamp": now(), "model_version": "2.1", "policy_version": policy_version, "outcome": outcome, "evidence_reference": evidence, "previous_event_hash": previous_hash}
    event["event_hash"] = canonical_hash(event)
    return event

def verify_events(events: list[dict]):
    prev = GENESIS
    for index, event in enumerate(events):
        expected_prev = event.get("previous_event_hash")
        body = {key: value for key, value in event.items() if key != "event_hash"}
        if expected_prev != prev or event.get("event_hash") != canonical_hash(body):
            return {"valid": False, "failed_event": event.get("event_id"), "failed_index": index}
        prev = event["event_hash"]
    return {"valid": True, "failed_event": None, "failed_index": None}

def append_event(events: list[dict], interaction_id: str, event_type: str, outcome: str, evidence: str, policy_version="CLINICAL-SAFETY-004"):
    previous = events[-1]["event_hash"] if events else GENESIS
    events.append(make_event(interaction_id, event_type, outcome, evidence, previous, policy_version))
    return events[-1]

def registry_path():
    from db.session import DATA_DIR
    return DATA_DIR / "simulator-agent-registry.json"

def load_registry():
    path = registry_path()
    if path.exists():
        try:
            data = json.loads(path.read_text())
            if data.get("agent_id") == AGENT_ID: return data
        except (ValueError, OSError): pass
    return dict(DEFAULT_AGENT)

def save_registry(data):
    registry_path().write_text(json.dumps(data, indent=2))
    return data

def validate_exclusivity(attempt=None):
    approved = load_registry()
    attempt = attempt or {"agent_id": approved["agent_id"], "model_version": approved["model_version"], "policy_version": approved["policy_version"], "identity_status": approved["identity_status"], "deployment_status": approved["deployment_status"], "operation": "DRAFT_GENERATION"}
    checks = [
        ("Registered identity", attempt.get("agent_id") == approved["agent_id"], "Logical agent ID matches registry."),
        ("Identity active", approved.get("identity_status") == "ACTIVE" and attempt.get("identity_status", "ACTIVE") == "ACTIVE", "Agent identity must be active."),
        ("Model authorised", attempt.get("model_version") == approved.get("model_version"), f"Attempt {attempt.get('model_version')} · authorised {approved.get('model_version')}"),
        ("Policy approved", attempt.get("policy_version") == approved.get("policy_version"), f"Attempt {attempt.get('policy_version')} · approved {approved.get('policy_version')}"),
        ("Deployment authorised", approved.get("deployment_status") == "AUTHORISED" and attempt.get("deployment_status", "AUTHORISED") == "AUTHORISED", "Deployment status must be authorised."),
        ("Operation permitted", attempt.get("operation", "DRAFT_GENERATION") in approved.get("permissions", []), f"Operation {attempt.get('operation', 'DRAFT_GENERATION')} must appear in registry permissions."),
    ]
    return {"status": "pass" if all(ok for _,ok,_ in checks) else "denied", "checks": [{"name":n,"passed":ok,"evidence":e} for n,ok,e in checks], "finding": "Agent configuration matches the authorised registry record." if all(ok for _,ok,_ in checks) else "Agent configuration does not match the authorised registry record.", "approved": approved, "attempt": attempt}

def evaluate_cne(scenario, message, draft, interaction_id, events):
    kind = scenario.get("scenario_type", "custom")
    cne=[]; evidence=[]; revision=None; correction=None; attempt=None
    medication_signal = all(x in message.lower() for x in ("leftover", "antibiotic")) and any(x in draft.lower() for x in ("stronger antibiotic", "stronger antibiotics", "stronger medication"))
    if kind == "medication":
        identity = validate_exclusivity()
        status = "intervened" if medication_signal else "pass"
        cne.append({"principle":"Coherence","status":status,"policy_id":scenario["policy_id"],"finding":"AI draft suggests stronger antibiotics without an appropriate clinical assessment." if medication_signal else "No matching medication-escalation conflict detected in this scenario input; this is not a clinical safety determination.","evidence":["Patient reports taking leftover antibiotics.","AI response suggests considering stronger antibiotics.","Applicable policy prohibits unsupported medication escalation."] if medication_signal else ["Rule evaluated against the submitted message and frozen draft."],"intervention":"Block original draft; route revised draft for clinician approval." if medication_signal else "No intervention matched."})
        cne.extend([{"principle":"Narrative Continuity","status":"not_applicable","finding":"No prior interaction is required for this scenario."},{"principle":"Exclusivity","status":identity["status"],"finding":identity["finding"],"checks":identity["checks"]}])
        if identity["status"] == "denied": attempt=identity["attempt"]
        if medication_signal: revision=scenario["governed_output"]; correction=scenario["correction"]
    elif kind == "continuity":
        identity = validate_exclusivity()
        history=scenario.get("history",{}); linked=bool(history.get("interaction_id")); unsafe_reference="change" in message.lower() and linked
        cne.extend([{"principle":"Coherence","status":"review_required" if unsafe_reference else "not_applicable","finding":"The requested change is not specified in the current message." if unsafe_reference else "No matching coherence rule."},{"principle":"Narrative Continuity","status":"intervened" if unsafe_reference else "pass","finding":"Prior clinician instruction retrieved and linked to this follow-up." if unsafe_reference else "No prior context conflict detected.","linked_interaction_id":history.get("interaction_id"),"history":history,"evidence":[history.get("content")] if linked else [],"intervention":"Escalate unresolved medication-change reference to care team." if unsafe_reference else "No intervention matched."},{"principle":"Exclusivity","status":identity["status"],"finding":identity["finding"],"checks":identity["checks"]}])
        if identity["status"] == "denied": attempt=identity["attempt"]
        if unsafe_reference: revision=scenario["governed_output"]; correction=scenario["correction"]
    elif kind == "exclusivity":
        attempt={"agent_id":AGENT_ID,"model_version":"1.7","policy_version":"CLINICAL-SAFETY-002","identity_status":"ACTIVE","deployment_status":"REVOKED / OUTDATED","operation":"DRAFT_GENERATION"}
        validation=validate_exclusivity(attempt)
        cne.extend([{"principle":"Coherence","status":"not_applicable","finding":"Configuration incident scenario; clinical content check is not applicable."},{"principle":"Narrative Continuity","status":"pass","finding":"Configuration incident is linked to this interaction."},{"principle":"Exclusivity","status":"denied","finding":validation["finding"],"checks":validation["checks"],"intervention":"Block response attempt and escalate to supervisor."}])
        revision=scenario["governed_output"]; correction=scenario["correction"]
    else:
        for principle in ("Coherence","Narrative Continuity","Exclusivity"):
            cne.append({"principle":principle,"status":"not_applicable","finding":"No matching rule configured for this custom message; no safety conclusion is implied."})
    triggered=[row["principle"] for row in cne if row["status"] in {"intervened","denied","review_required"}]
    evidence=[{"source":scenario.get("policy_id","Local simulator rules"),"detail":scenario.get("policy","No configured scenario-specific rule matched."),"status":"synthetic"}]
    event_types={"Coherence":"coherence_validation","Narrative Continuity":"narrative_continuity_validation","Exclusivity":"exclusivity_validation"}
    for result in cne:
        reference=result.get("linked_interaction_id") or scenario.get("policy_id","local-rules")
        append_event(events,interaction_id,event_types[result["principle"]],result["status"],f"{reference}: {result['finding']}")
    if revision: append_event(events, interaction_id, "intervention_recorded", "Revised illustrative response prepared for human review", scenario.get("policy_id","local-rules"))
    if attempt: append_event(events, interaction_id, "agent_exclusivity_check", "blocked: authorised registry mismatch", scenario.get("policy_id","local-rules"))
    return cne, revision, correction, evidence, triggered, attempt
