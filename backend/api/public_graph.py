"""Read-only knowledge-graph endpoints for the public web deployment.

Serves a pre-built, static SQLite file (`public_graph_seed/graph_corpus.sqlite3`,
produced by `scripts/export_public_graph.py`) rather than the live app database
or the full `api/graph.py` / `api/repository.py` routers. This deliberately
avoids pulling in chromadb/fastembed/pymupdf or any Moodle-corpus filesystem
access into the minimal public backend — there is no rebuild/import path here,
only reads over a fixed snapshot. The seed file already excludes the user's
own agent/conversation/memory nodes (private chat history) and never includes
`documents.file_path`, so the raw course PDFs are never reachable from this
process; `file_url` is always null and the frontend falls back to showing
extracted text instead of an embedded PDF viewer.
"""

import json
import sqlite3
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["public-graph"])

_SEED_PATH = Path(__file__).resolve().parent.parent / "public_graph_seed" / "graph_corpus.sqlite3"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{_SEED_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


@router.get("/graph/overview")
def graph_overview():
    conn = _conn()
    nodes = conn.execute("SELECT id, node_type, label, properties FROM graph_nodes").fetchall()
    edges = conn.execute(
        "SELECT id, source_id, target_id, relation, confidence, provenance FROM graph_edges"
    ).fetchall()
    conn.close()
    return {
        "nodes": [
            {
                "id": n["id"],
                "node_type": n["node_type"],
                "label": n["label"],
                "properties": json.loads(n["properties"] or "{}"),
            }
            for n in nodes
        ],
        "edges": [
            {
                "id": e["id"],
                "source": e["source_id"],
                "target": e["target_id"],
                "relation": e["relation"],
                "confidence": e["confidence"],
                "provenance": e["provenance"],
            }
            for e in edges
        ],
        "stats": {"node_count": len(nodes), "edge_count": len(edges)},
    }


@router.get("/graph/search")
def search_nodes(q: str, limit: int = 20):
    conn = _conn()
    rows = conn.execute(
        "SELECT id, node_type, label FROM graph_nodes WHERE label LIKE ? LIMIT ?",
        (f"%{q}%", limit),
    ).fetchall()
    conn.close()
    return {"nodes": [{"id": r["id"], "node_type": r["node_type"], "label": r["label"]} for r in rows]}


@router.get("/graph/nodes/{node_id}")
def node_detail(node_id: str):
    conn = _conn()
    node = conn.execute(
        "SELECT id, node_type, label, properties FROM graph_nodes WHERE id = ?", (node_id,)
    ).fetchone()
    if node is None:
        conn.close()
        raise HTTPException(404, "Node not found")

    edges = conn.execute(
        "SELECT id, source_id, target_id, relation, confidence, provenance FROM graph_edges "
        "WHERE source_id = ? OR target_id = ?",
        (node_id, node_id),
    ).fetchall()
    connections = []
    for e in edges:
        other_id = e["target_id"] if e["source_id"] == node_id else e["source_id"]
        direction = "outgoing" if e["source_id"] == node_id else "incoming"
        other = conn.execute(
            "SELECT id, node_type, label FROM graph_nodes WHERE id = ?", (other_id,)
        ).fetchone()
        if other is None:
            continue
        connections.append(
            {
                "edge_id": e["id"],
                "relation": e["relation"],
                "direction": direction,
                "provenance": e["provenance"],
                "confidence": e["confidence"],
                "node": {"id": other["id"], "node_type": other["node_type"], "label": other["label"]},
            }
        )
    conn.close()

    return {
        "id": node["id"],
        "node_type": node["node_type"],
        "label": node["label"],
        "properties": json.loads(node["properties"] or "{}"),
        "connections": connections,
    }


@router.get("/graph/nodes/{node_id}/sources")
def node_sources(node_id: str):
    conn = _conn()
    node = conn.execute(
        "SELECT id, node_type, label, properties FROM graph_nodes WHERE id = ?", (node_id,)
    ).fetchone()
    if node is None:
        conn.close()
        raise HTTPException(404, "Node not found")

    linked_ids: set[str] = set()
    case_ids: set[str] = set()
    if node["node_type"] == "document":
        linked_ids.add(node["id"])

    edges = conn.execute(
        "SELECT source_id, target_id FROM graph_edges WHERE source_id = ? OR target_id = ?",
        (node_id, node_id),
    ).fetchall()
    for e in edges:
        other_id = e["target_id"] if e["source_id"] == node_id else e["source_id"]
        other = conn.execute("SELECT id, node_type FROM graph_nodes WHERE id = ?", (other_id,)).fetchone()
        if other is None:
            continue
        if other["node_type"] == "document":
            linked_ids.add(other_id)
        elif other["node_type"] == "case":
            case_ids.add(other_id)

    if case_ids:
        placeholders = ",".join("?" * len(case_ids))
        rows = conn.execute(
            f"SELECT source_id, target_id FROM graph_edges "
            f"WHERE relation = 'SOURCED_FROM' AND source_id IN ({placeholders})",
            tuple(case_ids),
        ).fetchall()
        for r in rows:
            target = conn.execute(
                "SELECT id, node_type FROM graph_nodes WHERE id = ?", (r["target_id"],)
            ).fetchone()
            if target and target["node_type"] == "document":
                linked_ids.add(target["id"])

    documents = []
    seen: set[str] = set()
    for graph_doc_id in linked_ids:
        graph_doc = conn.execute(
            "SELECT id, label, properties FROM graph_nodes WHERE id = ?", (graph_doc_id,)
        ).fetchone()
        properties = json.loads(graph_doc["properties"] or "{}") if graph_doc else {}
        document_id = properties.get("document_id")
        document = (
            conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
            if document_id
            else None
        )
        if document is None and graph_doc is not None:
            candidates = conn.execute(
                "SELECT * FROM documents WHERE title = ?", (graph_doc["label"],)
            ).fetchall()
            if len(candidates) > 1:
                candidates = [
                    c
                    for c in candidates
                    if (not properties.get("course") or c["course"] == properties.get("course"))
                    and (not properties.get("term") or c["term"] == properties.get("term"))
                ]
            document = candidates[0] if candidates else None
        if document is None or document["id"] in seen:
            continue
        seen.add(document["id"])
        documents.append(
            {
                "id": document["id"],
                "title": document["title"],
                "file_type": document["file_type"],
                "term": document["term"],
                "course": document["course"],
                "category": document["category"],
                "page_count": document["page_count"],
                "file_url": None,
            }
        )
    conn.close()

    documents.sort(key=lambda d: (d["title"] or "").casefold())
    return {"documents": documents}


@router.get("/repository/documents/{doc_id}")
def document_detail(doc_id: str):
    conn = _conn()
    doc = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if doc is None:
        conn.close()
        raise HTTPException(404, "Document not found")
    chunks = conn.execute(
        "SELECT chunk_index, page_number, slide_number, text FROM document_chunks "
        "WHERE document_id = ? ORDER BY chunk_index",
        (doc_id,),
    ).fetchall()
    conn.close()

    tags = json.loads(doc["tags"] or "[]")
    return {
        "id": doc["id"],
        "title": doc["title"],
        "file_type": doc["file_type"],
        "term": doc["term"],
        "course": doc["course"],
        "course_code": doc["course_code"],
        "category": doc["category"],
        "material_type": tags[0] if tags else None,
        "page_count": doc["page_count"],
        "status": doc["status"],
        "error_message": None,
        "imported_at": doc["imported_at"],
        "last_indexed_at": doc["last_indexed_at"],
        "chunks": [
            {
                "chunk_index": c["chunk_index"],
                "page_number": c["page_number"],
                "slide_number": c["slide_number"],
                "text": c["text"],
            }
            for c in chunks
        ],
    }
