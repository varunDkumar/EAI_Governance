from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Agent, AgentPermission, Policy

OWNER = "varunnitt1411@gmail.com"

AGENTS = [
    {
        "slug": "course-tutor",
        "name": "Course Tutor",
        "description": "Explains academic concepts, frameworks and theories using approved textbooks and lecture notes.",
        "purpose": "Help the student understand course material through explanations, summaries and revision notes.",
        "permitted_tools": ["search_documents", "retrieve_memory", "create_memory_proposal"],
        "restricted_actions": ["access_case_studies", "access_restricted_collections", "modify_memory_without_approval"],
        "permissions": [
            ("material_type", "textbook", "read"),
            ("material_type", "lecture_notes", "read"),
            ("material_type", "general", "read"),
            ("memory_type", "knowledge", "read"),
            ("memory_type", "user_context", "read"),
            ("memory_type", "user_context", "write"),  # e.g. recording a learning gap it just identified
            ("memory_type", "episodic", "write"),  # what was discussed / left unresolved this session
        ],
    },
    {
        "slug": "case-analyst",
        "name": "Case Analyst",
        "description": "Analyses case studies, identifies business problems, compares frameworks and connects conclusions across cases.",
        "purpose": "Produce structured case analyses and cross-case comparisons grounded in the approved case library.",
        "permitted_tools": ["search_documents", "retrieve_memory", "create_memory_proposal", "compare_cases"],
        "restricted_actions": ["access_unrelated_personal_documents", "modify_governance_policies", "delete_memory"],
        "permissions": [
            ("material_type", "case_study", "read"),
            ("material_type", "textbook", "read"),
            ("memory_type", "knowledge", "read"),
            ("memory_type", "decision", "read"),
            ("memory_type", "episodic", "read"),
            ("memory_type", "decision", "write"),  # conclusions reached while analysing a case
            ("memory_type", "episodic", "write"),
        ],
    },
    {
        "slug": "exam-assistant",
        "name": "Exam Assistant",
        "description": "Prepares quizzes, generates mock questions and identifies learning gaps.",
        "purpose": "Track learning progress and generate practice material from approved textbooks and lecture material.",
        "permitted_tools": ["search_documents", "retrieve_memory", "create_memory_proposal", "generate_quiz"],
        "restricted_actions": ["access_other_collections", "modify_historical_learning_records_without_approval"],
        "permissions": [
            ("material_type", "textbook", "read"),
            ("material_type", "lecture_notes", "read"),
            ("memory_type", "user_context", "read"),
            ("memory_type", "user_context", "write"),
        ],
    },
]

POLICIES = [
    {
        "name": "collection-permission-required",
        "resource_type": "document",
        "condition": {"rule": "agent must hold a permission matching the document's material_type or category"},
        "effect": "DENY",
        "reason": "Agent has no permission covering this document's collection.",
        "priority": 100,
    },
    {
        "name": "restricted-category-block",
        "resource_type": "document",
        "condition": {"rule": "document.category == 'Restricted'"},
        "effect": "DENY",
        "reason": "Document belongs to the Restricted collection, which no agent may access automatically.",
        "priority": 10,
    },
    {
        "name": "protected-memory-modification",
        "resource_type": "memory",
        "condition": {"rule": "action == 'modify' and memory.approval_status == 'approved'"},
        "effect": "REQUIRE_APPROVAL",
        "reason": "Modifying an already-approved memory requires human sign-off.",
        "priority": 50,
    },
    {
        "name": "personal-memory-requires-approval",
        "resource_type": "memory",
        "condition": {"rule": "action == 'create' and memory_type == 'user_context'"},
        "effect": "REQUIRE_APPROVAL",
        "reason": "New persistent personal memories about a student always require human approval before being saved.",
        "priority": 40,
    },
    {
        "name": "suspended-agent-block",
        "resource_type": "*",
        "condition": {"rule": "agent.status != 'active'"},
        "effect": "DENY",
        "reason": "Agent is not active and cannot perform governed operations.",
        "priority": 1,
    },
]


def seed_if_empty(db: Session) -> None:
    """Idempotent: creates agents/permissions/policies that don't exist yet and
    leaves existing rows untouched, so it's safe to run on every startup and to
    pick up new permissions added to AGENTS/POLICIES without wiping real data
    (conversations, memories, audit history) tied to existing agent ids."""
    for spec in AGENTS:
        agent = db.execute(select(Agent).where(Agent.slug == spec["slug"])).scalar_one_or_none()
        if agent is None:
            agent = Agent(
                slug=spec["slug"],
                name=spec["name"],
                description=spec["description"],
                purpose=spec["purpose"],
                owner=OWNER,
                permitted_tools=spec["permitted_tools"],
                restricted_actions=spec["restricted_actions"],
            )
            db.add(agent)
            db.flush()

        existing = {
            (p.resource_type, p.resource_value, p.access_level)
            for p in db.execute(select(AgentPermission).where(AgentPermission.agent_id == agent.id)).scalars()
        }
        for resource_type, resource_value, access_level in spec["permissions"]:
            if (resource_type, resource_value, access_level) in existing:
                continue
            db.add(
                AgentPermission(
                    agent_id=agent.id,
                    resource_type=resource_type,
                    resource_value=resource_value,
                    access_level=access_level,
                )
            )

    existing_policy_names = {p.name for p in db.execute(select(Policy)).scalars()}
    for p in POLICIES:
        if p["name"] not in existing_policy_names:
            db.add(Policy(**p))

    db.commit()
