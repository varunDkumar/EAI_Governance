import json
import re
import threading
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Agent, Conversation, Document, GraphEdge, GraphNode, Memory, Message
from db.session import SessionLocal
from governance.policy_engine import ALLOW, evaluate_document_access
from llm.factory import get_provider

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()
_current_job_id: str | None = None

_CONCEPT_PROMPT = """Identify the key academic concepts and named frameworks/models covered in this \
document excerpt. A framework is a specific named model or theory (e.g. "Porter's Five Forces", \
"Capital Asset Pricing Model"); a concept is a more general idea or term (e.g. "opportunity cost", \
"market segmentation"). Extract at most 5 items, only ones genuinely central to this excerpt — skip \
generic administrative text (course outlines, author bios, citations).

If this is a business case study, also try to identify the company/organisation it is about.

Respond with ONLY strict JSON, no markdown fences:
{{"items": [{{"label": string, "type": "concept"|"framework"}}, ...], "company": string|null}}

Document: "{title}" (course: {course})
Excerpt:
{excerpt}
"""


def start_build() -> str:
    global _current_job_id
    with _jobs_lock:
        # Two concurrent builds would each load a stale node cache and
        # happily create duplicate-labelled nodes the other doesn't know
        # about yet — reuse the in-flight job instead of racing a new one.
        if _current_job_id is not None and _jobs.get(_current_job_id, {}).get("status") == "running":
            return _current_job_id
    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _current_job_id = job_id
        _jobs[job_id] = {
            "id": job_id,
            "status": "running",
            "total": 0,
            "processed": 0,
            "nodes_created": 0,
            "edges_created": 0,
            "errors": [],
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": None,
        }
    thread = threading.Thread(target=_run_build, args=(job_id,), daemon=True)
    thread.start()
    return job_id


def get_job(job_id: str) -> dict | None:
    with _jobs_lock:
        return dict(_jobs[job_id]) if job_id in _jobs else None


class _Counters:
    def __init__(self, job_id: str):
        self.job_id = job_id

    def bump(self, **kwargs):
        with _jobs_lock:
            for k, v in kwargs.items():
                self._jobs_job()[k] += v

    def _jobs_job(self):
        return _jobs[self.job_id]

    def set(self, **kwargs):
        with _jobs_lock:
            self._jobs_job().update(kwargs)


def _run_build(job_id: str) -> None:
    counters = _Counters(job_id)
    db = SessionLocal()
    try:
        cache = _load_node_cache(db)

        _sync_agent_nodes(db, cache, counters)
        documents = db.execute(select(Document).where(Document.status == "indexed")).scalars().all()
        counters.set(total=len(documents))

        provider = get_provider()
        for doc in documents:
            try:
                _sync_document_and_concepts(db, doc, cache, counters, provider)
            except Exception as e:  # noqa: BLE001 - one bad document must not stop the build
                with _jobs_lock:
                    _jobs[job_id]["errors"].append({"document": doc.title, "error": str(e)})
            finally:
                counters.bump(processed=1)

        _link_agent_access(db, cache, counters)
        _sync_memory_and_conversation_nodes(db, cache, counters)
        _link_concept_relations(db, counters)
        _link_conversation_concepts(db, cache, counters)
    finally:
        db.close()
        with _jobs_lock:
            _jobs[job_id]["status"] = "done"
            _jobs[job_id]["finished_at"] = datetime.now(timezone.utc).isoformat()


# The LLM extracts a per-excerpt "concept" vs "framework" classification, so
# the same real-world idea (e.g. "Root cause analysis") can come back typed
# differently across two different documents. Treating them as one dedup
# namespace means the label still only ever gets one node — whichever type it
# was first seen as — instead of a duplicate, disconnected twin node per type.
_MERGED_TYPE_GROUPS = {"concept": "concept_or_framework", "framework": "concept_or_framework"}


def _cache_key(node_type: str, label: str) -> tuple[str, str]:
    return (_MERGED_TYPE_GROUPS.get(node_type, node_type), label.strip().lower())


def _load_node_cache(db: Session) -> dict[tuple[str, str], str]:
    cache = {}
    for node in db.execute(select(GraphNode)).scalars():
        cache[_cache_key(node.node_type, node.label)] = node.id
    return cache


def _get_or_create_node(db: Session, cache: dict, counters: _Counters, node_type: str, label: str, properties: dict | None = None) -> str:
    key = _cache_key(node_type, label)
    if key in cache:
        return cache[key]
    node = GraphNode(node_type=node_type, label=label.strip(), properties=properties or {})
    db.add(node)
    db.flush()
    cache[key] = node.id
    counters.bump(nodes_created=1)
    return node.id


def _get_or_create_edge(db: Session, counters: _Counters, source_id: str, target_id: str, relation: str, *, confidence: float = 1.0, provenance: str = "inferred", source_ref: dict | None = None) -> None:
    existing = db.execute(
        select(GraphEdge).where(
            GraphEdge.source_id == source_id, GraphEdge.target_id == target_id, GraphEdge.relation == relation
        )
    ).scalar_one_or_none()
    if existing is not None:
        return
    db.add(
        GraphEdge(
            source_id=source_id,
            target_id=target_id,
            relation=relation,
            confidence=confidence,
            provenance=provenance,
            source_ref=source_ref or {},
        )
    )
    counters.bump(edges_created=1)


def _sync_agent_nodes(db: Session, cache: dict, counters: _Counters) -> None:
    for agent in db.execute(select(Agent)).scalars():
        _get_or_create_node(db, cache, counters, "agent", agent.name, {"agent_id": agent.id, "slug": agent.slug})
    db.commit()


def _sync_document_and_concepts(db: Session, doc: Document, cache: dict, counters: _Counters, provider) -> None:
    doc_node_id = _get_or_create_node(
        db,
        cache,
        counters,
        "document",
        doc.title,
        {"document_id": doc.id, "course": doc.course, "term": doc.term, "category": doc.category, "material_type": (doc.tags or [None])[0]},
    )
    db.commit()

    if not provider.is_configured():
        return

    excerpt = "\n".join(c.text for c in sorted(doc.chunks, key=lambda c: c.chunk_index)[:2])[:1500]
    if not excerpt.strip():
        return

    prompt = _CONCEPT_PROMPT.format(title=doc.title, course=doc.course or "unknown", excerpt=excerpt)
    try:
        raw = provider.generate(
            system_prompt="You extract academic concepts and frameworks from course material. Output strict JSON only.",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_retries=1,
        )
        parsed = _parse_json(raw)
    except Exception:  # noqa: BLE001 - extraction is best-effort per document
        return
    if not parsed:
        return

    material_type = (doc.tags or [None])[0]
    case_node_id = None
    if material_type == "case_study":
        case_node_id = _get_or_create_node(db, cache, counters, "case", doc.title, {"document_id": doc.id, "course": doc.course})
        _get_or_create_edge(db, counters, case_node_id, doc_node_id, "SOURCED_FROM", provenance="confirmed", confidence=1.0)
        company = parsed.get("company")
        if company:
            company_id = _get_or_create_node(db, cache, counters, "company", str(company))
            _get_or_create_edge(db, counters, case_node_id, company_id, "STUDIES", provenance="inferred", confidence=0.7, source_ref={"document_id": doc.id, "title": doc.title})

    for item in (parsed.get("items") or [])[:5]:
        label = str(item.get("label", "")).strip()
        if not label:
            continue
        item_type = "framework" if item.get("type") == "framework" else "concept"
        concept_id = _get_or_create_node(db, cache, counters, item_type, label)
        _get_or_create_edge(
            db, counters, doc_node_id, concept_id, "CONTAINS", provenance="inferred", confidence=0.7,
            source_ref={"document_id": doc.id, "title": doc.title},
        )
        if case_node_id and item_type == "framework":
            _get_or_create_edge(
                db, counters, case_node_id, concept_id, "ILLUSTRATES", provenance="inferred", confidence=0.6,
                source_ref={"document_id": doc.id, "title": doc.title},
            )
    db.commit()


def _link_agent_access(db: Session, cache: dict, counters: _Counters) -> None:
    agents = db.execute(select(Agent)).scalars().all()
    documents = db.execute(select(Document).where(Document.status == "indexed")).scalars().all()
    for agent in agents:
        agent_node_id = cache.get(("agent", agent.name.strip().lower()))
        if agent_node_id is None:
            continue
        for doc in documents:
            decision = evaluate_document_access(db, agent, doc, session_id="graph-build")
            if decision.effect != ALLOW:
                continue
            doc_node_id = cache.get(("document", doc.title.strip().lower()))
            if doc_node_id is None:
                continue
            _get_or_create_edge(db, counters, agent_node_id, doc_node_id, "ACCESSES", provenance="confirmed", confidence=1.0)
    db.commit()


def _sync_memory_and_conversation_nodes(db: Session, cache: dict, counters: _Counters) -> None:
    for memory in db.execute(select(Memory).where(Memory.approval_status == "approved")).scalars():
        node_type = "decision" if memory.memory_type == "decision" else "memory"
        memory_node_id = _get_or_create_node(db, cache, counters, node_type, memory.title, {"memory_id": memory.id, "memory_type": memory.memory_type})

        agent = db.get(Agent, memory.agent_id) if memory.agent_id else None
        if agent is not None:
            agent_node_id = cache.get(("agent", agent.name.strip().lower()))
            if agent_node_id:
                _get_or_create_edge(db, counters, agent_node_id, memory_node_id, "RETRIEVES", provenance="confirmed", confidence=1.0)

        if memory.conversation_id:
            conv = db.get(Conversation, memory.conversation_id)
            if conv is not None:
                conv_node_id = _get_or_create_node(db, cache, counters, "conversation", conv.title or "Conversation", {"conversation_id": conv.id})
                _get_or_create_edge(db, counters, memory_node_id, conv_node_id, "DERIVED_FROM", provenance="confirmed", confidence=1.0)

        for doc_id in memory.supporting_documents or []:
            doc = db.get(Document, doc_id)
            if doc is None:
                continue
            doc_node_id = cache.get(("document", doc.title.strip().lower()))
            if doc_node_id:
                _get_or_create_edge(db, counters, memory_node_id, doc_node_id, "SUPPORTED_BY", provenance="confirmed", confidence=1.0)
    db.commit()


def _link_concept_relations(db: Session, counters: _Counters) -> None:
    """Concepts that co-occur in the same document get a RELATED_TO edge."""
    rows = db.execute(
        select(GraphEdge.source_id, GraphEdge.target_id).where(GraphEdge.relation == "CONTAINS")
    ).all()
    by_doc: dict[str, list[str]] = {}
    for doc_id, concept_id in rows:
        by_doc.setdefault(doc_id, []).append(concept_id)

    for concept_ids in by_doc.values():
        for i in range(len(concept_ids)):
            for j in range(i + 1, len(concept_ids)):
                a, b = sorted([concept_ids[i], concept_ids[j]])
                _get_or_create_edge(db, counters, a, b, "RELATED_TO", provenance="inferred", confidence=0.5)
    db.commit()


def _link_conversation_concepts(db: Session, cache: dict, counters: _Counters) -> None:
    """Simple keyword match: if a concept/framework label appears in a
    conversation's messages, link Conversation DISCUSSES Concept."""
    concept_nodes = [(nid, label) for (ntype, label), nid in cache.items() if ntype in ("concept", "framework")]
    if not concept_nodes:
        return
    conversations = db.execute(select(Conversation)).scalars().all()
    for conv in conversations:
        messages = db.execute(select(Message).where(Message.conversation_id == conv.id)).scalars().all()
        text = " ".join(m.content for m in messages).lower()
        if not text:
            continue
        conv_node_id = cache.get(("conversation", (conv.title or "Conversation").strip().lower()))
        for concept_id, label in concept_nodes:
            if len(label) >= 4 and re.search(r"\b" + re.escape(label.lower()) + r"\b", text):
                if conv_node_id is None:
                    conv_node_id = _get_or_create_node(db, cache, counters, "conversation", conv.title or "Conversation", {"conversation_id": conv.id})
                _get_or_create_edge(db, counters, conv_node_id, concept_id, "DISCUSSES", provenance="inferred", confidence=0.6)
    db.commit()


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
