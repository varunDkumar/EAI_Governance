from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from db.models import Document, GraphEdge, GraphNode
from db.session import get_db
from graph import builder

router = APIRouter(prefix="/graph", tags=["graph"])


@router.post("/build")
def start_build():
    job_id = builder.start_build()
    return {"job_id": job_id}


@router.get("/build/status/{job_id}")
def build_status(job_id: str):
    job = builder.get_job(job_id)
    if job is None:
        raise HTTPException(404, "Unknown job id")
    return job


@router.get("/overview")
def graph_overview(node_type: str | None = None, limit: int = 2000, db: Session = Depends(get_db)):
    node_stmt = select(GraphNode)
    if node_type:
        node_stmt = node_stmt.where(GraphNode.node_type == node_type)
    nodes = db.execute(node_stmt.limit(limit)).scalars().all()
    node_ids = {n.id for n in nodes}

    edges = db.execute(select(GraphEdge)).scalars().all()
    edges = [e for e in edges if e.source_id in node_ids and e.target_id in node_ids]

    return {
        "nodes": [{"id": n.id, "node_type": n.node_type, "label": n.label, "properties": n.properties} for n in nodes],
        "edges": [
            {
                "id": e.id,
                "source": e.source_id,
                "target": e.target_id,
                "relation": e.relation,
                "confidence": e.confidence,
                "provenance": e.provenance,
            }
            for e in edges
        ],
        "stats": {"node_count": len(nodes), "edge_count": len(edges)},
    }


@router.get("/search")
def search_nodes(q: str, limit: int = 20, db: Session = Depends(get_db)):
    nodes = db.execute(select(GraphNode).where(GraphNode.label.ilike(f"%{q}%")).limit(limit)).scalars().all()
    return {"nodes": [{"id": n.id, "node_type": n.node_type, "label": n.label} for n in nodes]}


@router.get("/nodes/{node_id}/sources")
def node_sources(node_id: str, db: Session = Depends(get_db)):
    """Resolve a graph topic or case to its original Moodle source documents."""
    node = db.get(GraphNode, node_id)
    if node is None:
        raise HTTPException(404, "Node not found")

    nodes = {item.id: item for item in db.execute(select(GraphNode)).scalars()}
    edges = db.execute(select(GraphEdge)).scalars().all()
    linked_ids: set[str] = set()
    case_ids: set[str] = set()

    if node.node_type == "document":
        linked_ids.add(node.id)

    for edge in edges:
        if edge.source_id != node_id and edge.target_id != node_id:
            continue
        other_id = edge.target_id if edge.source_id == node_id else edge.source_id
        other = nodes.get(other_id)
        if other is None:
            continue
        if other.node_type == "document":
            linked_ids.add(other_id)
        elif other.node_type == "case":
            case_ids.add(other_id)

    if case_ids:
        for edge in edges:
            if edge.relation != "SOURCED_FROM" or edge.source_id not in case_ids:
                continue
            if nodes.get(edge.target_id) and nodes[edge.target_id].node_type == "document":
                linked_ids.add(edge.target_id)

    documents = []
    seen: set[str] = set()
    for graph_doc_id in linked_ids:
        graph_doc = nodes.get(graph_doc_id)
        document_id = (graph_doc.properties or {}).get("document_id") if graph_doc else None
        document = db.get(Document, document_id) if document_id else None
        # Older graph builds sometimes created a document node before the
        # source metadata was attached. The SOURCED_FROM edge still identifies
        # the source by title, so recover the Moodle row from that stable label.
        if document is None and graph_doc is not None:
            properties = graph_doc.properties or {}
            candidates = db.execute(
                select(Document).where(Document.title == graph_doc.label)
            ).scalars().all()
            if len(candidates) > 1:
                candidates = [
                    candidate for candidate in candidates
                    if (not properties.get("course") or candidate.course == properties.get("course"))
                    and (not properties.get("term") or candidate.term == properties.get("term"))
                ]
            document = candidates[0] if candidates else None
        if document is None or document.id in seen:
            continue
        seen.add(document.id)
        documents.append({
            "id": document.id,
            "title": document.title,
            "file_type": document.file_type,
            "term": document.term,
            "course": document.course,
            "category": document.category,
            "page_count": document.page_count,
            "file_url": f"/repository/documents/{document.id}/file" if document.file_type.lower() == "pdf" else None,
        })

    documents.sort(key=lambda item: (item["title"] or "").casefold())
    return {"documents": documents}


@router.get("/nodes/{node_id}")
def node_detail(node_id: str, db: Session = Depends(get_db)):
    node = db.get(GraphNode, node_id)
    if node is None:
        raise HTTPException(404, "Node not found")

    edges = db.execute(
        select(GraphEdge).where(or_(GraphEdge.source_id == node_id, GraphEdge.target_id == node_id))
    ).scalars().all()

    connections = []
    for e in edges:
        other_id = e.target_id if e.source_id == node_id else e.source_id
        direction = "outgoing" if e.source_id == node_id else "incoming"
        other = db.get(GraphNode, other_id)
        if other is None:
            continue
        connections.append(
            {
                "edge_id": e.id,
                "relation": e.relation,
                "direction": direction,
                "provenance": e.provenance,
                "confidence": e.confidence,
                "node": {"id": other.id, "node_type": other.node_type, "label": other.label},
            }
        )

    return {
        "id": node.id,
        "node_type": node.node_type,
        "label": node.label,
        "properties": node.properties,
        "connections": connections,
    }
