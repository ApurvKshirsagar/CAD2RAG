import time
import uuid
from typing import Optional
from app.config import settings

# In-memory store: session_id -> session dict
_store: dict = {}

# ── Single-file session (legacy / kept for compatibility) ────────────

def create_session(file_type: str, data: dict) -> str:
    session_id = str(uuid.uuid4())
    _store[session_id] = {
        "session_type": "single",
        "file_type": file_type,
        "data": data,
        "created_at": time.time(),
    }
    return session_id


def get_session(session_id: str) -> Optional[dict]:
    session = _store.get(session_id)
    if not session:
        return None
    age = time.time() - session["created_at"]
    if age > settings.session_ttl_seconds:
        del _store[session_id]
        return None
    return session


# ── Multi-file batch session ─────────────────────────────────────────

def create_batch_session() -> str:
    """Create an empty batch session and return its ID."""
    session_id = str(uuid.uuid4())
    _store[session_id] = {
        "session_type": "batch",
        "files": [],          # list of {file_type, filename, data, summary}
        "created_at": time.time(),
    }
    return session_id


def add_file_to_batch(session_id: str, file_type: str, filename: str, data: dict, summary: dict) -> bool:
    """Append a processed file into an existing batch session. Returns False if not found."""
    session = get_session(session_id)
    if not session or session.get("session_type") != "batch":
        return False
    session["files"].append({
        "file_type": file_type,
        "filename": filename,
        "data": data,
        "summary": summary,
    })
    return True


# ── Shared helpers ───────────────────────────────────────────────────

def delete_session(session_id: str):
    _store.pop(session_id, None)


def cleanup_expired():
    now = time.time()
    expired = [
        sid for sid, s in _store.items()
        if now - s["created_at"] > settings.session_ttl_seconds
    ]
    for sid in expired:
        del _store[sid]
