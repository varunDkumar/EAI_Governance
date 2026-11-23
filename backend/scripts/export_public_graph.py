"""One-time export: build a small, self-contained SQLite file with only the
course-content portion of the knowledge graph (concepts, frameworks, cases,
companies, documents and their extracted text), for the public web deployment.

Deliberately excludes:
- `agent` / `conversation` / `memory` graph nodes — these are the user's own
  chat history and agent registry, not course content, and must never be public.
- `documents.file_path` — a local filesystem path, not useful publicly.

Also adds "course" hub nodes (see `add_course_bridges`): diagnostics showed
the real concept/framework/case/company graph (via RELATED_TO/ILLUSTRATES/
STUDIES edges alone) is genuinely fragmented into 65 components, the largest
only 17 nodes — not a visualisation artifact, but a property of how the
underlying LLM extraction works per document excerpt with no cross-document
linking step. Rather than inventing semantic links, we add one node per
course (verified metadata already on every document) and connect each
concept/framework/case/company to the course(s) its source document(s)
belong to. That alone collapses the 65 fragments to 30, with the two largest
at 77 and 49 nodes.

Run from `backend/`: python scripts/export_public_graph.py
"""

import json
import sqlite3
from collections import defaultdict
from pathlib import Path

SRC_DB = Path(__file__).resolve().parent.parent / "data" / "app.db"
OUT_DIR = Path(__file__).resolve().parent.parent / "public_graph_seed"
OUT_DB = OUT_DIR / "graph_corpus.sqlite3"

KEEP_NODE_TYPES = ("concept", "framework", "case", "company", "document")
DOMAIN_TYPES = ("concept", "framework", "case", "company")
EVIDENCE_RELATIONS = ("CONTAINS", "SOURCED_FROM", "DISCUSSES")


def add_course_bridges(dst: sqlite3.Connection) -> int:
    nodes = dst.execute("SELECT id, node_type, properties FROM graph_nodes").fetchall()
    domain_ids = {row[0] for row in nodes if row[1] in DOMAIN_TYPES}
    doc_course = {
        row[0]: (json.loads(row[2] or "{}") or {}).get("course")
        for row in nodes
        if row[1] == "document"
    }

    placeholders = ",".join("?" * len(EVIDENCE_RELATIONS))
    evidence_edges = dst.execute(
        f"SELECT source_id, target_id FROM graph_edges WHERE relation IN ({placeholders})",
        EVIDENCE_RELATIONS,
    ).fetchall()

    concept_to_courses: dict[str, set[str]] = defaultdict(set)
    for source_id, target_id in evidence_edges:
        if source_id in domain_ids and doc_course.get(target_id):
            concept_to_courses[source_id].add(doc_course[target_id])
        if target_id in domain_ids and doc_course.get(source_id):
            concept_to_courses[target_id].add(doc_course[source_id])

    course_names = sorted({c for courses in concept_to_courses.values() for c in courses})
    course_node_id = {name: f"course:{i}" for i, name in enumerate(course_names)}

    dst.executemany(
        "INSERT INTO graph_nodes VALUES (?,?,?,?)",
        [(node_id, "course", name, json.dumps({})) for name, node_id in course_node_id.items()],
    )
    bridge_edges = [
        (f"course-edge:{concept_id}:{course_node_id[course]}", concept_id, course_node_id[course],
         "USED_IN_COURSE", 1.0, "confirmed")
        for concept_id, courses in concept_to_courses.items()
        for course in courses
    ]
    dst.executemany("INSERT INTO graph_edges VALUES (?,?,?,?,?,?)", bridge_edges)
    return len(course_names)


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    OUT_DB.unlink(missing_ok=True)

    src = sqlite3.connect(str(SRC_DB))
    dst = sqlite3.connect(str(OUT_DB))

    dst.execute(
        "CREATE TABLE graph_nodes (id TEXT PRIMARY KEY, node_type TEXT, label TEXT, properties TEXT)"
    )
    dst.execute(
        "CREATE TABLE graph_edges (id TEXT PRIMARY KEY, source_id TEXT, target_id TEXT, "
        "relation TEXT, confidence REAL, provenance TEXT)"
    )
    dst.execute(
        "CREATE TABLE documents (id TEXT PRIMARY KEY, title TEXT, file_type TEXT, term TEXT, "
        "course TEXT, course_code TEXT, category TEXT, tags TEXT, page_count INTEGER, "
        "status TEXT, imported_at TEXT, last_indexed_at TEXT)"
    )
    dst.execute(
        "CREATE TABLE document_chunks (id TEXT PRIMARY KEY, document_id TEXT, chunk_index INTEGER, "
        "page_number INTEGER, slide_number INTEGER, text TEXT)"
    )

    placeholders = ",".join("?" * len(KEEP_NODE_TYPES))
    kept_nodes = src.execute(
        f"SELECT id, node_type, label, properties FROM graph_nodes WHERE node_type IN ({placeholders})",
        KEEP_NODE_TYPES,
    ).fetchall()
    kept_ids = {row[0] for row in kept_nodes}
    dst.executemany("INSERT INTO graph_nodes VALUES (?,?,?,?)", kept_nodes)

    all_edges = src.execute(
        "SELECT id, source_id, target_id, relation, confidence, provenance FROM graph_edges"
    ).fetchall()
    kept_edges = [e for e in all_edges if e[1] in kept_ids and e[2] in kept_ids]
    dst.executemany("INSERT INTO graph_edges VALUES (?,?,?,?,?,?)", kept_edges)

    documents = src.execute(
        "SELECT id, title, file_type, term, course, course_code, category, tags, page_count, "
        "status, imported_at, last_indexed_at FROM documents"
    ).fetchall()
    dst.executemany("INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", documents)
    document_ids = {row[0] for row in documents}

    chunks = src.execute(
        "SELECT id, document_id, chunk_index, page_number, slide_number, text FROM document_chunks"
    ).fetchall()
    kept_chunks = [c for c in chunks if c[1] in document_ids]
    dst.executemany("INSERT INTO document_chunks VALUES (?,?,?,?,?,?)", kept_chunks)

    course_count = add_course_bridges(dst)

    dst.commit()
    src.close()
    dst.close()

    print(f"Wrote {OUT_DB}")
    print(f"  graph_nodes: {len(kept_nodes)} (excluded agent/conversation/memory)")
    print(f"  graph_edges: {len(kept_edges)} (of {len(all_edges)} total)")
    print(f"  course bridge nodes added: {course_count}")
    print(f"  documents: {len(documents)}")
    print(f"  document_chunks: {len(kept_chunks)}")
    print(f"  file size: {OUT_DB.stat().st_size / 1_000_000:.1f} MB")


if __name__ == "__main__":
    main()
