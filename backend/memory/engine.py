import json
import re

from sqlalchemy.orm import Session

from db.models import Agent, Approval, Memory, MemorySource
from governance.policy_engine import ALLOW, DENY, REQUIRE_APPROVAL, evaluate_memory_read, evaluate_memory_write
from ingest.chroma_store import get_memories_collection
from ingest.embeddings import embed_texts
from llm.factory import get_provider

MEMORY_TYPES = {"knowledge", "episodic", "user_context", "decision"}
RETRIEVAL_K = 6

_PROPOSAL_PROMPT = """You just finished one exchange with a student as an AI agent. Decide whether \
anything from it is worth remembering for future sessions (a learning gap, a concept explained, a \
conclusion reached, a preference). Most exchanges are NOT worth remembering — only propose a memory \
for something genuinely reusable, not routine Q&A.

Respond with ONLY strict JSON, no markdown fences, matching exactly this shape:
{{"should_remember": boolean, "memory_type": "knowledge"|"episodic"|"user_context"|"decision", \
"title": string (<10 words), "description": string (1-2 sentences), "topic": string, "confidence": number between 0 and 1}}

If nothing is worth remembering, respond {{"should_remember": false}} and omit the other fields.

Student: {user_content}
{agent_name}: {assistant_content}
"""


def propose_memory(
    db: Session,
    agent: Agent,
    conversation_id: str,
    user_content: str,
    assistant_content: str,
    citations: list[dict] | None = None,
) -> Memory | None:
    """Best-effort: an LLM call decides if this exchange is worth remembering,
    then the proposal goes through the same governance gate as any other
    memory write (never auto-trusted as approved)."""
    provider = get_provider()
    if not provider.is_configured():
        return None

    prompt = _PROPOSAL_PROMPT.format(
        user_content=user_content[:1000], assistant_content=assistant_content[:1500], agent_name=agent.name
    )
    try:
        raw = provider.generate(
            system_prompt="You extract durable memories from tutoring conversations. Output strict JSON only.",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_retries=1,  # best-effort: skip it rather than make the user wait out a rate-limit retry
        )
        parsed = _parse_json(raw)
    except Exception:  # noqa: BLE001 - memory proposal must never break the chat response
        return None

    if not parsed or not parsed.get("should_remember"):
        return None

    memory_type = parsed.get("memory_type")
    if memory_type not in MEMORY_TYPES:
        return None

    decision = evaluate_memory_write(db, agent, memory_type, is_modification=False, session_id=conversation_id)
    if decision.effect == DENY:
        return None  # agent has no standing permission to propose this memory type at all

    supporting_document_ids = list({c["document_id"] for c in (citations or []) if c.get("document_id")})

    memory = Memory(
        memory_type=memory_type,
        title=str(parsed.get("title", "Untitled memory"))[:200],
        description=str(parsed.get("description", "")),
        topic=parsed.get("topic"),
        agent_id=agent.id,
        conversation_id=conversation_id,
        confidence=float(parsed.get("confidence", 0.6) or 0.6),
        approval_status="approved" if decision.effect == ALLOW else "pending",
        supporting_documents=supporting_document_ids,
    )
    db.add(memory)
    db.flush()
    db.add(MemorySource(memory_id=memory.id, source_type="conversation", source_id=conversation_id))
    for doc_id in supporting_document_ids:
        db.add(MemorySource(memory_id=memory.id, source_type="document", source_id=doc_id))

    if decision.effect == REQUIRE_APPROVAL:
        db.add(
            Approval(
                agent_id=agent.id,
                action="create_memory",
                resource_type="memory",
                resource_id=memory.id,
                reason=decision.reason,
                policy_id=decision.policy,
            )
        )

    db.commit()
    db.refresh(memory)

    if memory.approval_status == "approved":
        index_memory(memory)

    return memory


def index_memory(memory: Memory) -> None:
    """Embed an approved memory into the vector store so it can be retrieved."""
    [vector] = embed_texts([f"{memory.title}. {memory.description}"])
    collection = get_memories_collection()
    collection.upsert(
        ids=[memory.id],
        embeddings=[vector],
        documents=[memory.description],
        metadatas=[
            {
                "memory_id": memory.id,
                "title": memory.title,
                "memory_type": memory.memory_type,
                "topic": memory.topic or "",
            }
        ],
    )


def unindex_memory(memory_id: str) -> None:
    collection = get_memories_collection()
    try:
        collection.delete(ids=[memory_id])
    except Exception:  # noqa: BLE001 - fine if it was never indexed
        pass


def retrieve_memories_with_governance(db: Session, agent: Agent, query: str) -> tuple[list[dict], list[dict]]:
    collection = get_memories_collection()
    if collection.count() == 0:
        return [], []
    [vector] = embed_texts([query])
    results = collection.query(query_embeddings=[vector], n_results=min(RETRIEVAL_K, collection.count()))

    ids = results.get("ids", [[]])[0]
    metas = results.get("metadatas", [[]])[0]

    used: list[dict] = []
    notes: list[dict] = []
    for memory_id, meta in zip(ids, metas):
        memory = db.get(Memory, memory_id)
        if memory is None:
            continue
        decision = evaluate_memory_read(db, agent, memory, session_id=agent.id)
        if decision.effect != ALLOW:
            notes.append({"memory_id": memory_id, "title": meta.get("title"), "decision": decision.effect, "reason": decision.reason})
            continue
        used.append(
            {
                "memory_id": memory.id,
                "title": memory.title,
                "description": memory.description,
                "memory_type": memory.memory_type,
                "topic": memory.topic,
            }
        )
    return used, notes


def _parse_json(raw: str) -> dict | None:
    text = raw.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except (json.JSONDecodeError, ValueError):
                return None
        return None
