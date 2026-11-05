from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy.orm import Session
from db.models import SimulatorApproval, SimulatorComparison, SimulatorExecution
from governance.audit import log_event
from .cne import GENESIS, append_event, evaluate_cne, load_registry
from .scenarios import SCENARIOS

def execute_comparison(db: Session, scenario_id: str, patient_message: str | None = None, role: str = "Nurse / Clinician"):
    scenario = dict(SCENARIOS.get(scenario_id) or {})
    if not scenario and scenario_id != "custom": return None
    if scenario_id == "custom":
        scenario={"id":"custom","name":"Custom synthetic message","principle":"Custom","user_input":patient_message or "","scenario_type":"custom","policy_id":"LOCAL_RULES_NONE","policy":"Custom inputs receive only configured local checks. No matching rule does not imply clinical safety."}
    message=patient_message if patient_message is not None else scenario["user_input"]
    scenario["user_input"]=message
    if scenario.get("scenario_type")=="exclusivity": attempt_text="1.7 / CLINICAL-SAFETY-002 (revoked/outdated)"; draft=scenario["initial_output"]
    elif scenario.get("scenario_type")=="medication": attempt_text="2.1 / CLINICAL-SAFETY-004"; draft=scenario["initial_output"]
    elif scenario.get("scenario_type")=="continuity": attempt_text="2.1 / CLINICAL-SAFETY-004"; draft="I can't see the relevant earlier instruction in this message. Please contact your care team before making any medication changes." if patient_message and patient_message != SCENARIOS[scenario_id]["user_input"] else scenario["initial_output"]
    else:
        attempt_text="2.1 / CLINICAL-SAFETY-004"
        draft="Thank you for your message. I can help route your question to the care team, who can review the details and respond." if message else "Please enter a synthetic message to generate an illustrative draft."
    interaction_id=str(uuid4()); now=datetime.now(timezone.utc).isoformat(); registry=load_registry()
    context={"synthetic":True,"patient_id":scenario.get("patient_id","SYN-CUSTOM"),"model_version":"2.1","policy_version":"CLINICAL-SAFETY-004","agent_id":registry["agent_id"],"ai_output_label":"Deterministic illustrative simulation","interaction_id":interaction_id,"same_frozen_draft_both_paths":True}
    # One generated draft is persisted identically on the two executions.
    baseline_id=str(uuid4()); governed_id=str(uuid4()); events=[]
    append_event(events,interaction_id,"patient_query_received","synthetic input received",scenario_id)
    append_event(events,interaction_id,"initial_ai_response_generated","one frozen draft generated",f"draft-sha256-source:{uuid4()}")
    cne,revision,correction,evidence,triggered,attempt=evaluate_cne(scenario,message,draft,interaction_id,events)
    baseline_timeline=[{"phase":"Patient query received","at":now},{"phase":"Shared AI draft generated","at":now},{"phase":"Draft placed in clinician inbox","at":now},{"phase":"Conventional review: approved without substantive modification","at":now},{"phase":"Original illustrative response marked sent in simulation","at":now}]
    baseline=SimulatorExecution(id=baseline_id,comparison_id="",execution_mode="baseline",status="simulated_sent",initial_input=message,initial_context=context,initial_output=draft,final_output=draft,cne_results=[],evidence=[],decision="ALLOW",deliverable=False,access_attempts=[],timeline=baseline_timeline)
    governed_context=dict(context); governed_context.update({"retrieved_history":scenario.get("history"),"agent_attempt":attempt})
    if attempt:
        governed_output=scenario["governed_output"]; status="blocked"; decision="DENY"; approval_status="escalated"
    else:
        governed_output=revision or draft; status="awaiting_human_approval"; decision="REQUIRE_APPROVAL"; approval_status="pending"
    # Rebuild timeline from the hash-chained event records; approval is appended later.
    governed=SimulatorExecution(id=governed_id,comparison_id="",execution_mode="governed",status=status,initial_input=message,initial_context=governed_context,initial_output=draft,final_output=governed_output,cne_results=cne,evidence=evidence,correction_instruction=correction,decision=decision,deliverable=False,access_attempts=[],timeline=events)
    comparison=SimulatorComparison(scenario_id=scenario_id,scenario_name=scenario["name"],agent_id=registry["agent_id"],agent_name=registry["logical_identity"],model_label=attempt_text,demo_mode=True,initial_input=message,final_decision=decision,approval_status=approval_status,baseline_execution_id=baseline_id,governed_execution_id=governed_id,principles_triggered=triggered)
    db.add(comparison); db.flush(); baseline.comparison_id=comparison.id; governed.comparison_id=comparison.id; db.add_all([baseline,governed]); db.flush()
    if not attempt:
        db.add(SimulatorApproval(comparison_id=comparison.id,scenario_id=scenario_id,agent_name=registry["logical_identity"],initial_output=draft,corrected_output=governed_output,findings=cne,evidence=evidence))
    db.commit(); db.refresh(comparison)
    log_event(db,event_type="simulator_comparison_created",agent_id=registry["agent_id"],resource_id=comparison.id,decision=decision,reason=f"Synthetic shared-draft comparison executed for {scenario_id}")
    return comparison.id

def comparison_detail(db: Session, comparison: SimulatorComparison):
    executions=db.query(SimulatorExecution).filter_by(comparison_id=comparison.id).all()
    approvals=db.query(SimulatorApproval).filter_by(comparison_id=comparison.id).all()
    scenario=SCENARIOS.get(comparison.scenario_id) or {"id":"custom","name":comparison.scenario_name,"user_input":comparison.initial_input,"principle":"Custom","policy_id":"LOCAL_RULES_NONE","policy":"Custom messages have no matching scenario-specific rule by default."}
    from .cne import verify_events
    governed=next((e for e in executions if e.execution_mode=="governed"),None)
    return {"comparison":comparison,"executions":{e.execution_mode:e for e in executions},"approvals":approvals,"scenario":scenario,"interaction_verification":verify_events(governed.timeline if governed else [])}
