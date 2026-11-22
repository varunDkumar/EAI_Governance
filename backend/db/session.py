import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# Resolving this from __file__ breaks once the backend is frozen (PyInstaller):
# __file__ then points inside the bundle's own _internal/ copy, so a packaged
# app would silently create a fresh, empty database instead of using the real
# one. ATF_DATA_DIR lets whoever launches the backend (the Tauri sidecar, a
# packaged .app) pin this explicitly; dev mode falls back to the old relative
# path for convenience.
DATA_DIR = Path(os.environ["ATF_DATA_DIR"]) if os.environ.get("ATF_DATA_DIR") else Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "app.db"

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False, "timeout": 15},
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, _record):
    # WAL lets the background importer write while the API serves reads/chat
    # concurrently, instead of "database is locked" under the default journal mode.
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
