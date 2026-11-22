# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

The primary audience is stakeholders evaluating an academic AI product presentation. They need to understand the memory experience and see how governance changes an AI agent's behavior.

## Product Purpose

Agent Trust Fabric demonstrates two connected but distinct product experiences: Memory Intelligence for persistent agent context and knowledge work, and Governance Simulator for comparing agent outcomes with and without the CNE protocol.

## Positioning

The product presents persistent agent memory alongside a governance demonstration that makes validation, correction, access decisions, human oversight, and audit records visible.

## Operating Context

The existing desktop app is a local-first academic intelligence workspace over the IIMA course repository. The presentation entry should offer Memory Intelligence and Governance Simulator as separate experiences. The simulator demonstrates a fictional hospital's AI-assisted patient inbox using synthetic scenarios based on a classroom case.

## Capabilities and Constraints

- The Memory Intelligence product includes an AI workspace, academic repository, persistent memory, approvals, governance policies, audit history, and a knowledge graph.
- The Governance Simulator compares an ungoverned response with a CNE-governed response to the same healthcare scenario and synthetic data.
- CNE means Coherence, Narrative Continuity, and Exclusivity.
- The simulator uses deterministic dummy data. Simulated responses and decisions must be labeled illustrative and must not be presented as clinical advice or live model output.
- The simulator must keep its synthetic healthcare data separate from the academic repository and existing memory records.
- The user supplied the case study "Inbox Intervention: Should AI Help Clinicians Respond to Patients?" as reference material; the build must use original synthetic demonstration content rather than reproduce the copyrighted case.
- The primary policy-contradiction example is a patient question involving leftover antibiotics. Other examples demonstrate forgotten historical context and a patient-record access boundary.

## Brand Commitments

- Product name: Agent Trust Fabric.
- Existing edition label: Academic Intelligence Edition.
- Retain the current app identity and interface language for these additions.

## Evidence on Hand

- Existing implementation: `app/` and `backend/`.
- Academic source material: `moodle-bak/`.
- User-supplied classroom case reference: `/Users/dvss/Downloads/Inbox Intervention Should AI Help Clinicians Respond to Patients_.pdf`.
- The simulator's healthcare records, policies, agent responses, and execution results are synthetic; they are not clinical validation.
- No independently validated customer outcomes or benchmark claims are available in this project.

## Product Principles

1. Show Memory Intelligence and Governance Simulator as distinct, understandable product experiences.
2. Compare governance outcomes using identical scenario input and initial context.
3. Explain a governed decision with the triggered CNE principle, evidence, intervention, and resulting action.
4. Keep synthetic healthcare data clearly separate from real academic workspace data.
5. Preserve the existing memory, repository, agent, and audit capabilities.
