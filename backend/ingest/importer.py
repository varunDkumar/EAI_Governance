import hashlib
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from db.models import Document, DocumentChunk
from db.session import SessionLocal

from .chroma_store import get_document_chunks_collection
from .chunking import Chunk, chunk_units
from .classify import SUPPORTED_EXTENSIONS, classify_category, classify_material_type, extract_course_code
from .embeddings import embed_texts
from .parsers import ParseError, extract

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()

MAX_CHUNKS_PER_DOCUMENT = 400
EMBED_BATCH_SIZE = 64


def _embed_in_batches(texts: list[str]) -> list[list[float]]:
    """Embeds in fixed-size batches rather than all at once, bounding peak
    memory for very large documents instead of materialising every chunk's
    tokenized representation and vector simultaneously."""
    vectors: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        vectors.extend(embed_texts(texts[i : i + EMBED_BATCH_SIZE]))
    return vectors


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def start_job(corpus_root: Path, import_path: Path) -> str:
    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {
            "id": job_id,
            "status": "running",
            "total": 0,
            "processed": 0,
            "indexed": 0,
            "skipped_duplicates": 0,
            "errors": [],
            "current_file": None,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": None,
        }
    thread = threading.Thread(target=_run_job, args=(job_id, corpus_root, import_path), daemon=True)
    thread.start()
    return job_id


def get_job(job_id: str) -> dict | None:
    with _jobs_lock:
        return dict(_jobs[job_id]) if job_id in _jobs else None


def _run_job(job_id: str, corpus_root: Path, import_path: Path) -> None:
    files = [p for p in import_path.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS]
    with _jobs_lock:
        _jobs[job_id]["total"] = len(files)

    db = SessionLocal()
    collection = get_document_chunks_collection()
    try:
        for path in files:
            with _jobs_lock:
                _jobs[job_id]["current_file"] = path.name
            try:
                _import_one(db, collection, corpus_root, path)
                with _jobs_lock:
                    _jobs[job_id]["indexed"] += 1
            except _DuplicateFile:
                with _jobs_lock:
                    _jobs[job_id]["skipped_duplicates"] += 1
            except Exception as e:  # noqa: BLE001 - one bad file must not stop the import
                with _jobs_lock:
                    _jobs[job_id]["errors"].append({"file": str(path), "error": str(e)})
            finally:
                with _jobs_lock:
                    _jobs[job_id]["processed"] += 1
    finally:
        db.close()
        with _jobs_lock:
            _jobs[job_id]["status"] = "done"
            _jobs[job_id]["current_file"] = None
            _jobs[job_id]["finished_at"] = datetime.now(timezone.utc).isoformat()


class _DuplicateFile(Exception):
    pass


def _import_one(db, collection, corpus_root: Path, path: Path) -> None:
    file_hash = _hash_file(path)
    existing = db.execute(select(Document).where(Document.file_hash == file_hash)).scalar_one_or_none()
    if existing is not None:
        raise _DuplicateFile()

    rel_parts = path.relative_to(corpus_root).parts
    term = rel_parts[0] if len(rel_parts) > 0 else None
    course = rel_parts[1] if len(rel_parts) > 1 else None
    relative_path = str(path.relative_to(corpus_root))

    category = classify_category(course or "")
    material_type = classify_material_type(relative_path, path.name)
    course_code = extract_course_code(course or "")
    document_id = str(uuid.uuid4())

    # Do all CPU/IO-bound work (parsing, chunking, embedding) BEFORE opening any
    # DB transaction, so the write lock is only held for the final, fast insert —
    # not for the many seconds a big document's embedding pass can take, which
    # would otherwise starve concurrent writers (e.g. a chat request) past their
    # busy_timeout under SQLite's one-writer-at-a-time rule (even with WAL).
    error_message: str | None = None
    page_count: int | None = None
    chunks: list = []
    vectors: list = []
    try:
        units, page_count = extract(path)
        chunks = chunk_units(units)
        if len(chunks) > MAX_CHUNKS_PER_DOCUMENT:
            # An outlier document (e.g. a 300+ page annual report) can produce
            # thousands of chunks; embedding them all at once has been observed
            # to exhaust memory on constrained hardware and stall the whole
            # backend. Index a bounded prefix instead of failing the import or
            # risking the app's stability — still searchable, just not complete.
            original_count = len(chunks)
            chunks = chunks[:MAX_CHUNKS_PER_DOCUMENT]
            chunks.append(
                Chunk(
                    text=(
                        f"[Note: this document produced {original_count} passages — unusually large. "
                        f"Only the first {MAX_CHUNKS_PER_DOCUMENT} were indexed for search, to protect "
                        "system performance.]"
                    ),
                    page_number=None,
                    slide_number=None,
                )
            )
        if chunks:
            vectors = _embed_in_batches([c.text for c in chunks])
    except ParseError as e:
        error_message = str(e)

    document = Document(
        id=document_id,
        title=path.stem,
        file_path=str(path),
        file_hash=file_hash,
        file_type=path.suffix.lower().lstrip("."),
        term=term,
        course=course,
        course_code=course_code,
        category=category,
        tags=[material_type],
        page_count=page_count,
        status="error" if error_message else "indexed",
        error_message=error_message,
        last_indexed_at=None if error_message else datetime.now(timezone.utc),
    )
    db.add(document)

    if error_message or not chunks:
        db.commit()
        return

    chroma_ids = []
    chroma_texts = []
    chroma_embeddings = []
    chroma_metadatas = []

    for idx, (chunk, vector) in enumerate(zip(chunks, vectors)):
        chroma_id = str(uuid.uuid4())
        db_chunk = DocumentChunk(
            document_id=document.id,
            chunk_index=idx,
            page_number=chunk.page_number,
            slide_number=chunk.slide_number,
            text=chunk.text,
            chroma_id=chroma_id,
        )
        db.add(db_chunk)

        chroma_ids.append(chroma_id)
        chroma_texts.append(chunk.text)
        chroma_embeddings.append(vector)
        chroma_metadatas.append(
            {
                "document_id": document.id,
                "title": document.title,
                "course": course or "",
                "term": term or "",
                "category": category,
                "material_type": material_type,
                "page_number": chunk.page_number or 0,
                "slide_number": chunk.slide_number or 0,
            }
        )

    collection.add(
        ids=chroma_ids,
        embeddings=chroma_embeddings,
        documents=chroma_texts,
        metadatas=chroma_metadatas,
    )

    db.commit()
