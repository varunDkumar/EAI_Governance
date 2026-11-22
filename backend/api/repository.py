import os
import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from fastapi.responses import FileResponse

from db.models import Document
from db.session import get_db
from ingest import importer
from ingest.chroma_store import get_document_chunks_collection
from ingest.embeddings import embed_texts

router = APIRouter(prefix="/repository", tags=["repository"])

CORPUS_ROOT = (
    Path(os.environ["ATF_CORPUS_ROOT"])
    if os.environ.get("ATF_CORPUS_ROOT")
    else Path(__file__).resolve().parent.parent.parent / "moodle-bak"
)


class ImportRequest(BaseModel):
    subpath: str = ""  # e.g. "Term 1", or "" for the whole corpus


@router.get("/terms")
def list_terms():
    if not CORPUS_ROOT.exists():
        return {"terms": []}
    terms = []
    for term_dir in sorted(p for p in CORPUS_ROOT.iterdir() if p.is_dir()):
        courses = sorted(p.name for p in term_dir.iterdir() if p.is_dir())
        terms.append({"name": term_dir.name, "courses": courses})
    return {"terms": terms}


@router.post("/import")
def start_import(req: ImportRequest):
    target = (CORPUS_ROOT / req.subpath).resolve()
    if not str(target).startswith(str(CORPUS_ROOT.resolve())):
        raise HTTPException(400, "Invalid import path")
    if not target.exists() or not target.is_dir():
        raise HTTPException(404, f"Folder not found: {req.subpath}")
    job_id = importer.start_job(CORPUS_ROOT, target)
    return {"job_id": job_id}


@router.get("/import/status/{job_id}")
def import_status(job_id: str):
    job = importer.get_job(job_id)
    if job is None:
        raise HTTPException(404, "Unknown job id")
    return job


@router.get("/documents")
def list_documents(
    term: str | None = None,
    course: str | None = None,
    category: str | None = None,
    status: str | None = None,
    q: str | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    stmt = select(Document)
    if term:
        stmt = stmt.where(Document.term == term)
    if course:
        stmt = stmt.where(Document.course == course)
    if category:
        stmt = stmt.where(Document.category == category)
    if status:
        stmt = stmt.where(Document.status == status)
    if q:
        stmt = stmt.where(Document.title.ilike(f"%{q}%"))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    stmt = stmt.order_by(Document.imported_at.desc()).limit(limit).offset(offset)
    docs = db.execute(stmt).scalars().all()
    return {
        "total": total,
        "documents": [_doc_to_dict(d) for d in docs],
    }


@router.get("/documents/{doc_id}")
def get_document(doc_id: str, db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(404, "Document not found")
    payload = _doc_to_dict(doc)
    payload["chunks"] = [
        {
            "chunk_index": c.chunk_index,
            "page_number": c.page_number,
            "slide_number": c.slide_number,
            "text": c.text,
        }
        for c in sorted(doc.chunks, key=lambda c: c.chunk_index)
    ]
    return payload


@router.get("/documents/{doc_id}/file")
def get_document_file(doc_id: str, db: Session = Depends(get_db)):
    """Serve an imported source file inline for the repository's in-app viewer."""
    doc = db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(404, "Document not found")
    path = Path(doc.file_path).resolve()
    try:
        path.relative_to(CORPUS_ROOT.resolve())
    except ValueError as exc:
        raise HTTPException(403, "Document is outside the configured course corpus") from exc
    if not path.is_file():
        raise HTTPException(404, "The source file is no longer available in moodle-bak")
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=path.name, content_disposition_type="inline")


@router.get("/search")
def search_documents(q: str, limit: int = 10):
    if not q.strip():
        return {"results": []}
    collection = get_document_chunks_collection()
    if collection.count() == 0:
        return {"results": []}
    [vector] = embed_texts([q])
    results = collection.query(query_embeddings=[vector], n_results=min(limit, collection.count()))
    out = []
    ids = results.get("ids", [[]])[0]
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    dists = results.get("distances", [[]])[0]
    for chunk_id, text, meta, dist in zip(ids, docs, metas, dists):
        out.append(
            {
                "chunk_id": chunk_id,
                "snippet": text[:400],
                "document_id": meta.get("document_id"),
                "title": meta.get("title"),
                "course": meta.get("course"),
                "page_number": meta.get("page_number") or None,
                "slide_number": meta.get("slide_number") or None,
                "score": 1 - dist,
            }
        )
    return {"results": out}


@router.get("/stats")
def repository_stats(db: Session = Depends(get_db)):
    total = db.execute(select(func.count()).select_from(Document)).scalar_one()
    indexed = db.execute(select(func.count()).select_from(Document).where(Document.status == "indexed")).scalar_one()
    errored = db.execute(select(func.count()).select_from(Document).where(Document.status == "error")).scalar_one()
    by_category = db.execute(select(Document.category, func.count()).group_by(Document.category)).all()
    by_term = db.execute(select(Document.term, func.count()).group_by(Document.term)).all()
    return {
        "total": total,
        "indexed": indexed,
        "errored": errored,
        "by_category": {c or "Uncategorised": n for c, n in by_category},
        "by_term": {t or "Unknown": n for t, n in by_term},
    }


def _doc_to_dict(d: Document) -> dict:
    return {
        "id": d.id,
        "title": d.title,
        "file_type": d.file_type,
        "term": d.term,
        "course": d.course,
        "course_code": d.course_code,
        "category": d.category,
        "material_type": (d.tags or [None])[0],
        "page_count": d.page_count,
        "status": d.status,
        "error_message": d.error_message,
        "imported_at": d.imported_at.isoformat() if d.imported_at else None,
        "last_indexed_at": d.last_indexed_at.isoformat() if d.last_indexed_at else None,
    }
