"""One-time export: build a small, self-contained SQLite file with only the
course-content portion of the knowledge graph (concepts, frameworks, cases,
companies, documents and their extracted text), for the public web deployment.

Deliberately excludes:
- `agent` / `conversation` / `memory` graph nodes — these are the user's own
  chat history and agent registry, not course content, and must never be public.
- `documents.file_path` — a local filesystem path, not useful publicly.

Run from `backend/`: python scripts/export_public_graph.py
"""

import sqlite3
from pathlib import Path

SRC_DB = Path(__file__).resolve().parent.parent / "data" / "app.db"
OUT_DIR = Path(__file__).resolve().parent.parent / "public_graph_seed"
OUT_DB = OUT_DIR / "graph_corpus.sqlite3"

KEEP_NODE_TYPES = ("concept", "framework", "case", "company", "document")


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

    dst.commit()
    src.close()
    dst.close()

    print(f"Wrote {OUT_DB}")
    print(f"  graph_nodes: {len(kept_nodes)} (excluded agent/conversation/memory)")
    print(f"  graph_edges: {len(kept_edges)} (of {len(all_edges)} total)")
    print(f"  documents: {len(documents)}")
    print(f"  document_chunks: {len(kept_chunks)}")
    print(f"  file size: {OUT_DB.stat().st_size / 1_000_000:.1f} MB")


if __name__ == "__main__":
    main()
