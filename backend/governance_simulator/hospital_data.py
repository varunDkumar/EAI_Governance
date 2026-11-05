"""Synthetic, deterministic Apollo Hospital / CNE patient-journey fixture data.

Entirely illustrative: a fictional hospital, a fictional patient, and
hand-authored clinical text. No live model or clinical system is involved —
see PRODUCT.md. Used once to seed the cne_* tables (see journey_engine.py).
"""

HOSPITAL = {
    "name": "Apollo Multispeciality Hospital",
    "departments": [
        "Internal Medicine",
        "Respiratory Medicine",
        "Radiology",
        "Pathology and Laboratory",
        "Pharmacy",
        "Orthopaedics",
        "Nursing and Patient Care",
        "Hospital Administration",
    ],
}

PATIENT = {
    "patient_code": "PAT-10482",
    "name": "Rajesh Kumar",
    "age": 46,
    "gender": "Male",
    "blood_group": "O+",
    "registered_date": "2026-11-05",
    "medical_history": ["Hypertension"],
    "medications": ["Amlodipine"],
}

EPISODES = [
    {"key": "respiratory", "name": "Respiratory illness", "status": "closed", "opened_at": "2026-11-05", "closed_at": "2026-11-26"},
    {"key": "orthopaedic", "name": "Orthopaedic — knee injury", "status": "open", "opened_at": "2027-02-15", "closed_at": None},
]

# --- Policy building blocks (spec §5C: department / task / patient level) --

DEPARTMENT_POLICIES = {
    "respiratory": "Respiratory Medicine clinical workflow policy",
    "orthopaedic": "Orthopaedic clinical workflow policy",
    "lab": "Laboratory and diagnostic workflow policy",
    "pharmacy": "Pharmacy dispensing workflow policy",
    "admin": "Hospital administration data-handling policy",
}

TASK_POLICIES = {
    "triage": "Triage intake and symptom-capture protocol",
    "documentation": "Clinical documentation and transcription protocol",
    "diagnostic": "Diagnostic interpretation support rules",
    "treatment": "Treatment recommendation constraints",
    "medication_safety": "Medication safety and interaction-check rules",
    "prescription": "Prescription drafting constraints (physician sign-off required)",
    "followup": "Follow-up scheduling protocol",
    "governance": "Agent identity and audit oversight protocol",
}

PATIENT_POLICIES = [
    "Patient consent and data-access permission",
    "Existing medication record (Amlodipine)",
    "Recorded allergy list (none on file)",
    "Patient-specific clinical restrictions",
    "Cross-episode data-sharing permission",
]


def _policy_set(department_keys: list[str], task_key: str) -> dict:
    return {
        "department": [DEPARTMENT_POLICIES[k] for k in department_keys],
        "task": [TASK_POLICIES[task_key]],
        "patient": list(PATIENT_POLICIES),
    }


AGENTS = [
    {
        "key": "triage", "name": "AI Triage Agent", "cof_id": "COF-TRIAGE-001",
        "substrate_anchor": "SA-HOSP-001", "substrate_label": "Hospital AI Compute Node 01",
        "runtime": "Triage AI Runtime v1.4",
        "responsibility": "Patient interactions, symptom collection and preliminary clinical summaries.",
        "policy_set": _policy_set(["respiratory", "orthopaedic"], "triage"),
    },
    {
        "key": "documentation", "name": "AI Clinical Documentation Agent", "cof_id": "COF-DOCS-001",
        "substrate_anchor": "SA-HOSP-002", "substrate_label": "Hospital AI Compute Node 02",
        "runtime": "Documentation AI Runtime v1.2",
        "responsibility": "Doctor-patient consultation transcription and clinical notes.",
        "policy_set": _policy_set(["respiratory", "orthopaedic"], "documentation"),
    },
    {
        "key": "diagnostic", "name": "AI Diagnostic Support Agent", "cof_id": "COF-DIAG-001",
        "substrate_anchor": "SA-HOSP-004", "substrate_label": "Hospital AI Compute Node 04",
        "runtime": "Diagnostic AI Runtime v2.1",
        "responsibility": "Interpretation of laboratory and radiology reports.",
        "policy_set": _policy_set(["lab"], "diagnostic"),
    },
    {
        "key": "treatment", "name": "AI Treatment Recommendation Agent", "cof_id": "COF-TREAT-001",
        "substrate_anchor": "SA-HOSP-005", "substrate_label": "Hospital AI Compute Node 05",
        "runtime": "Treatment AI Runtime v1.8",
        "responsibility": "Suggested treatment plans based on clinical context.",
        "policy_set": _policy_set(["respiratory", "orthopaedic"], "treatment"),
    },
    {
        "key": "prescription", "name": "AI Prescription Support Agent", "cof_id": "COF-PRESCRIPTION-001",
        "substrate_anchor": "SA-HOSP-006", "substrate_label": "Hospital AI Compute Node 06",
        "runtime": "Prescription AI Runtime v1.3",
        "responsibility": "Drafting prescriptions for physician approval.",
        "policy_set": _policy_set(["pharmacy"], "prescription"),
    },
    {
        "key": "medication_safety", "name": "AI Medication Safety Agent", "cof_id": "COF-MEDSAFETY-001",
        "substrate_anchor": "SA-HOSP-007", "substrate_label": "Hospital AI Compute Node 07",
        "runtime": "Medication Safety AI Runtime v1.5",
        "responsibility": "Checking prescriptions against existing medication and allergy records.",
        "policy_set": _policy_set(["pharmacy"], "medication_safety"),
    },
    {
        "key": "followup", "name": "AI Follow-up Agent", "cof_id": "COF-FOLLOWUP-001",
        "substrate_anchor": "SA-HOSP-008", "substrate_label": "Hospital AI Compute Node 08",
        "runtime": "Follow-up AI Runtime v1.1",
        "responsibility": "Monitoring follow-ups and patient progress.",
        "policy_set": _policy_set(["respiratory", "orthopaedic"], "followup"),
    },
    {
        "key": "governance", "name": "AI Governance Agent", "cof_id": "COF-GOVERNANCE-001",
        "substrate_anchor": "SA-HOSP-009", "substrate_label": "Hospital AI Compute Node 09",
        "runtime": "Governance AI Runtime v1.0",
        "responsibility": "Monitoring agent identities, policies, actions and audit trails.",
        "policy_set": _policy_set(["admin"], "governance"),
    },
]

# --- Encounters (visits), each with an ordered workflow-stage sequence -----
# `coherence` marks stages where new evidence revises an earlier belief —
# these get an RbR proof capsule in the with_cne scenario (spec §6A).

ENCOUNTERS = [
    {
        "key": "visit1", "episode": "respiratory", "encounter_code": "ENC-0001", "visit_date": "2026-11-05",
        "department": "Respiratory Medicine", "doctor_name": "Dr. Meera Sharma",
        "chief_complaint": "Persistent cough, mild fever, fatigue, difficulty breathing during physical activity.",
        "stages": [
            {"stage": "triage", "agent": "triage", "consumed_by": "Dr. Meera Sharma",
             "input_refs": ["Patient chat transcript"],
             "output": "Patient reports a persistent cough for 5 days, mild fever (~99.8°F), fatigue and breathlessness on exertion. No chest pain reported. Preliminary summary: possible lower respiratory tract infection; recommend clinical examination and baseline diagnostics."},
            {"stage": "documentation", "agent": "documentation", "consumed_by": "Respiratory Medicine department",
             "input_refs": ["Triage summary", "Consultation audio"],
             "output": "Dr. Meera Sharma examined the patient. Auscultation notes mild bilateral crackles at the lung bases. Vitals: BP 138/88, SpO2 96% on room air, temp 99.9°F. Clinical impression: suspected respiratory infection, pending diagnostics. CBC, CRP and chest X-ray ordered."},
            {"stage": "diagnostic", "agent": "diagnostic", "consumed_by": "Dr. Meera Sharma",
             "input_refs": ["CBC report", "CRP report", "Chest X-ray"], "coherence": True,
             "output": "CBC shows a mildly elevated WBC count (11,200/µL). CRP is elevated at 18 mg/L, consistent with an active inflammatory process. Chest X-ray shows mild peribronchial thickening in the right lower lobe, no consolidation. Interpretation: findings are consistent with an uncomplicated lower respiratory tract infection, likely bronchitis."},
            {"stage": "treatment", "agent": "treatment", "consumed_by": "Dr. Meera Sharma",
             "input_refs": ["Confirmed diagnosis"], "coherence": True,
             "output": "Recommend a 5-day course of an appropriate oral antibiotic, an antipyretic for fever, and rest with adequate hydration. Advise review in one week if symptoms persist, or sooner if breathlessness worsens. No evidence currently supports hospitalisation."},
            {"stage": "medication_safety", "agent": "medication_safety", "consumed_by": "Pharmacy",
             "input_refs": ["Existing medication: Amlodipine", "Treatment plan"],
             "output": "Cross-checked proposed treatment against the patient's existing medication record: Amlodipine (for hypertension). No documented interaction between the recommended antibiotic class and Amlodipine. No recorded allergies on file. Safety check: cleared."},
            {"stage": "prescription", "agent": "prescription", "consumed_by": "Dr. Meera Sharma",
             "input_refs": ["Approved treatment plan", "Medication safety check"],
             "output": "Draft prescription: Amoxicillin-Clavulanate 625mg, twice daily for 5 days; Paracetamol 650mg as needed for fever, max 3x/day. Continue existing Amlodipine as prescribed. Draft prepared for physician approval."},
            {"stage": "followup", "agent": "followup", "consumed_by": "Rajesh Kumar",
             "input_refs": ["Approved prescription"],
             "output": "Follow-up consultation scheduled for 12 November 2026 to reassess cough and treatment response. Patient advised to return sooner if breathlessness worsens or fever persists beyond 3 days."},
        ],
    },
    {
        "key": "visit2", "episode": "respiratory", "encounter_code": "ENC-0002", "visit_date": "2026-11-12",
        "department": "Respiratory Medicine", "doctor_name": "Dr. Arjun Rao",
        "chief_complaint": "Persistent cough despite completed antibiotic course; follow-up visit.",
        "stages": [
            {"stage": "triage", "agent": "triage", "consumed_by": "Dr. Arjun Rao",
             "input_refs": ["Patient chat transcript", "05 Nov visit record"],
             "output": "Patient returns reporting the cough has persisted despite completing the prescribed antibiotic course; fever has resolved. Mild fatigue remains. Preliminary summary: incomplete response to initial treatment; recommend re-assessment and comparison against the 05 Nov visit."},
            {"stage": "documentation", "agent": "documentation", "consumed_by": "Respiratory Medicine department",
             "input_refs": ["Triage summary", "05 Nov consultation record"],
             "output": "Dr. Arjun Rao reviewed the patient, noting the prior 05 Nov consultation, diagnostics and treatment course. Auscultation now clear bilaterally. Vitals: BP 134/86, SpO2 98% on room air, temp 98.4°F (afebrile). Clinical impression: residual post-infective cough; ordering a repeat CRP and chest X-ray for comparison."},
            {"stage": "diagnostic", "agent": "diagnostic", "consumed_by": "Dr. Arjun Rao",
             "input_refs": ["05 Nov CRP (18 mg/L)", "05 Nov chest X-ray", "12 Nov CRP report", "12 Nov chest X-ray"], "coherence": True,
             "output": "Repeat CRP has fallen to 6 mg/L (from 18 mg/L on 05 Nov), indicating resolving inflammation. Chest X-ray shows resolution of the prior peribronchial thickening. Compared against the 05 Nov report: findings support a resolving infection with a lingering post-infective cough, rather than a new or ongoing infection."},
            {"stage": "treatment", "agent": "treatment", "consumed_by": "Dr. Arjun Rao",
             "input_refs": ["Updated diagnostic interpretation"], "coherence": True,
             "output": "Given the improving inflammatory markers and radiographic resolution, recommend symptomatic management only: a short course of a cough suppressant and continued rest. No further antibiotics indicated at this time, as the prior course has been effective. Advise follow-up in two weeks to confirm resolution."},
            {"stage": "medication_safety", "agent": "medication_safety", "consumed_by": "Pharmacy",
             "input_refs": ["Existing medication: Amlodipine", "Completed antibiotic course", "Updated treatment plan"],
             "output": "Cross-checked updated treatment against the patient's existing medication record: Amlodipine (ongoing), prior antibiotic course (completed 09 Nov). No interaction flagged between the proposed cough suppressant and current medications. Safety check: cleared."},
            {"stage": "prescription", "agent": "prescription", "consumed_by": "Dr. Arjun Rao",
             "input_refs": ["Approved treatment plan", "Medication safety check"],
             "output": "Draft prescription: dextromethorphan-based cough syrup, as directed, for up to 7 days. Continue existing Amlodipine as prescribed. Draft prepared for physician approval."},
            {"stage": "followup", "agent": "followup", "consumed_by": "Rajesh Kumar",
             "input_refs": ["Approved prescription"],
             "output": "Follow-up consultation scheduled for 26 November 2026 to confirm symptom resolution and consider closing the respiratory episode."},
        ],
    },
    {
        "key": "visit3", "episode": "respiratory", "encounter_code": "ENC-0003", "visit_date": "2026-11-26",
        "department": "Respiratory Medicine", "doctor_name": "Dr. Arjun Rao",
        "chief_complaint": "Follow-up review for the respiratory illness episode.",
        "stages": [
            {"stage": "triage", "agent": "triage", "consumed_by": "Dr. Arjun Rao",
             "input_refs": ["Patient chat transcript", "12 Nov visit record"],
             "output": "Patient reports the cough has fully resolved; no fever, no breathlessness, energy levels back to normal. Preliminary summary: symptomatic recovery reported; recommend clinical confirmation before closing the episode."},
            {"stage": "diagnostic", "agent": "diagnostic", "consumed_by": "Dr. Arjun Rao",
             "input_refs": ["05 Nov CRP/X-ray", "12 Nov CRP/X-ray", "Patient-reported recovery"], "coherence": True,
             "output": "Reviewing the full respiratory episode: CRP trend 18 → 6 mg/L and chest X-ray findings resolved between the 05 Nov and 12 Nov visits, consistent with the patient-reported full recovery today. No further diagnostics indicated."},
            {"stage": "documentation", "agent": "documentation", "consumed_by": "Respiratory Medicine department",
             "input_refs": ["05 Nov visit record", "12 Nov visit record", "Updated diagnostic review"],
             "output": "Doctor reviewed the patient's progress against both prior visits (05 Nov, 12 Nov). Clinical examination unremarkable, vitals within normal range. Treatment response documented as complete. Clinical impression: respiratory episode resolved."},
            {"stage": "followup", "agent": "followup", "consumed_by": "Rajesh Kumar",
             "input_refs": ["Episode closure note"],
             "output": "Respiratory illness episode closed as clinically resolved. Patient advised to return if symptoms recur. No further scheduled follow-up for this episode."},
        ],
    },
    {
        "key": "visit4", "episode": "orthopaedic", "encounter_code": "ENC-0004", "visit_date": "2027-02-15",
        "department": "Orthopaedics", "doctor_name": "Dr. Vikram",
        "chief_complaint": "Right knee pain and swelling following a sports injury.",
        "stages": [
            {"stage": "triage", "agent": "triage", "consumed_by": "Dr. Vikram",
             "input_refs": ["Patient chat transcript"],
             "output": "Patient reports right knee pain and mild swelling following a sports injury two days ago. No prior knee complaints on file. Preliminary summary: suspected soft-tissue or ligament injury; recommend orthopaedic examination and imaging."},
            {"stage": "documentation", "agent": "documentation", "consumed_by": "Orthopaedics department",
             "input_refs": ["Triage summary", "Consultation audio"],
             "output": "Dr. Vikram examined the patient's right knee: mild swelling, tenderness over the medial joint line, limited range of motion, no gross instability on exam. Vitals unremarkable. Clinical impression: suspected medial meniscus or ligament strain. X-ray ordered to rule out fracture."},
            {"stage": "diagnostic", "agent": "diagnostic", "consumed_by": "Dr. Vikram",
             "input_refs": ["Right knee X-ray"], "coherence": True,
             "output": "Right knee X-ray shows no fracture or bony abnormality. Soft-tissue swelling noted, consistent with the reported injury mechanism. Interpretation: findings support a soft-tissue strain rather than a bony injury; clinical correlation with exam findings recommended."},
            {"stage": "treatment", "agent": "treatment", "consumed_by": "Dr. Vikram",
             "input_refs": ["Confirmed diagnosis"], "coherence": True,
             "output": "Recommend RICE protocol (rest, ice, compression, elevation), a short course of an anti-inflammatory, and a knee brace for support. Advise physiotherapy referral if symptoms do not improve within two weeks. No surgical indication at this time."},
            {"stage": "medication_safety", "agent": "medication_safety", "consumed_by": "Pharmacy",
             "input_refs": ["Existing medication: Amlodipine", "Treatment plan"],
             "output": "Cross-checked proposed anti-inflammatory against the patient's existing medication record: Amlodipine (ongoing, for hypertension). Flagged for physician awareness: some anti-inflammatory classes can modestly reduce antihypertensive effectiveness; a renally-favourable option and blood-pressure monitoring are recommended. No allergies on file."},
            {"stage": "prescription", "agent": "prescription", "consumed_by": "Dr. Vikram",
             "input_refs": ["Approved treatment plan", "Medication safety check"],
             "output": "Draft prescription: topical anti-inflammatory gel for the knee, short-course oral analgesic as needed, knee brace. Continue existing Amlodipine as prescribed; advise home blood-pressure monitoring for two weeks given the interaction note above. Draft prepared for physician approval."},
            {"stage": "followup", "agent": "followup", "consumed_by": "Rajesh Kumar",
             "input_refs": ["Approved prescription"],
             "output": "Follow-up consultation scheduled for 01 March 2027 to assess knee recovery and review blood pressure readings. Orthopaedic episode remains open pending recovery confirmation."},
        ],
    },
]
