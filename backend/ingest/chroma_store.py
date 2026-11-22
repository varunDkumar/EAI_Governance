import threading

from db.session import DATA_DIR

_client = None
_client_lock = threading.Lock()

CHROMA_DIR = DATA_DIR / "chroma"


def get_client():
    global _client
    if _client is None:
        # The import job's background thread and request-handling threads can
        # both reach here on first use; without a lock, two concurrent
        # PersistentClient(...) calls race inside chromadb's shared system
        # registry and raise a KeyError.
        with _client_lock:
            if _client is None:
                import chromadb

                CHROMA_DIR.mkdir(parents=True, exist_ok=True)
                _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _client


def get_document_chunks_collection():
    return get_client().get_or_create_collection("document_chunks")


def get_memories_collection():
    return get_client().get_or_create_collection("memories")
