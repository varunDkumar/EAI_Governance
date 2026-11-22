import logging
from contextlib import asynccontextmanager

from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logger = logging.getLogger("agent_trust_fabric")

# find_dotenv() walks up from the current working directory rather than from
# __file__, which (like DATA_DIR in db/session.py) would resolve inside the
# PyInstaller bundle's _internal/ copy once frozen. Whoever launches the
# backend (dev script, Tauri sidecar) sets cwd to the real backend/ folder.
load_dotenv(find_dotenv(usecwd=True))

from api.agents import router as agents_router  # noqa: E402
from api.approvals import router as approvals_router  # noqa: E402
from api.audit import router as audit_router  # noqa: E402
from api.chat import router as chat_router  # noqa: E402
from api.governance import router as governance_router  # noqa: E402
from api.graph import router as graph_router  # noqa: E402
from api.memory import router as memory_router  # noqa: E402
from api.overview import router as overview_router  # noqa: E402
from api.repository import router as repository_router  # noqa: E402
from api.simulator import router as simulator_router  # noqa: E402
from db.models import AppSession  # noqa: E402
from db.session import Base, SessionLocal, engine  # noqa: E402
from db.seed import seed_if_empty  # noqa: E402
from governance.audit import log_event  # noqa: E402
from llm.factory import get_provider  # noqa: E402

APP_VERSION = "0.1.0-mvp"
_app_session_id: str | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _app_session_id
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_if_empty(db)
        session = AppSession(kind="app")
        db.add(session)
        db.commit()
        db.refresh(session)
        _app_session_id = session.id
        log_event(db, event_type="app_startup", session_id=_app_session_id, decision="ALLOW", reason="Application started")
    finally:
        db.close()

    yield

    db = SessionLocal()
    try:
        log_event(db, event_type="app_shutdown", session_id=_app_session_id, decision="ALLOW", reason="Application shutting down")
        if _app_session_id:
            session = db.get(AppSession, _app_session_id)
            if session:
                from datetime import datetime, timezone

                session.ended_at = datetime.now(timezone.utc)
                db.commit()
    finally:
        db.close()


app = FastAPI(title="Agent Trust Fabric Backend", version=APP_VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:1420", "tauri://localhost", "http://tauri.localhost"],
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(repository_router)
app.include_router(agents_router)
app.include_router(chat_router)
app.include_router(governance_router)
app.include_router(memory_router)
app.include_router(approvals_router)
app.include_router(audit_router)
app.include_router(graph_router)
app.include_router(overview_router)
app.include_router(simulator_router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Database errors, unexpected library failures, etc. must never crash the
    process or leak a stack trace to the client — log server-side, return a
    clean, generic message to the UI."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected server error occurred. Check the backend logs for details."},
    )


@app.get("/health")
def health():
    provider = get_provider()
    return {
        "status": "ok",
        "version": APP_VERSION,
        "llm_provider": provider.name,
        "llm_configured": provider.is_configured(),
    }


if __name__ == "__main__":
    # Lets the PyInstaller-bundled executable actually start a server when
    # double-clicked/spawned — `python -m uvicorn main:app` (used in dev) never
    # hits this block, since it imports main as a module rather than running it.
    import os

    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("ATF_PORT", "8756")))
