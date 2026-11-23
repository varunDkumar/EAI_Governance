"""Minimal public-facing backend: Governance Simulator + a read-only Knowledge
Graph demo.

Deliberately does NOT import the live Memory Intelligence stack (the ingest/
chat pipeline, fastembed, chromadb, pymupdf, the LLM provider factory, or any
Moodle-corpus filesystem access) — that stack is desktop-only. The Knowledge
Graph here is served from a pre-built, static snapshot
(`public_graph_seed/graph_corpus.sqlite3`, see `api/public_graph.py` and
`scripts/export_public_graph.py`) with no rebuild/import path and no raw PDF
file serving, so none of the heavy ingestion dependencies are needed. The
Governance Simulator is unrelated: fully deterministic, synthetic,
hand-authored data (see governance_simulator/hospital_data.py) with zero LLM
calls.

This keeps the public deployment's dependency list (see
requirements-public.txt) and memory footprint small enough for a free-tier
host, and — just as importantly — means the corpus ingestion/LLM code paths
are physically absent from what's running publicly, not just unlinked from
the UI.
"""

import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.public_graph import router as public_graph_router
from api.simulator import router as simulator_router
from db.session import Base, engine

APP_VERSION = "0.1.0-public-demo"

app = FastAPI(title="Agent Trust Fabric — Governance Simulator (public demo)", version=APP_VERSION)

# Space-separated list of allowed origins, e.g. "https://my-app.vercel.app".
# Falls back to allowing any origin, since this backend only ever serves
# synthetic demo data — there is nothing on it that needs origin-locking.
_cors_origins = os.environ.get("ATF_PUBLIC_CORS_ORIGINS", "").split()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(simulator_router)
app.include_router(public_graph_router)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": "An unexpected server error occurred."})


@app.get("/health")
def health():
    return {"status": "ok", "version": APP_VERSION, "mode": "public-demo"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8756")))
