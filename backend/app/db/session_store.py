import time
import uuid
from typing import Optional
from app.config import settings

# In-memory store: session_id -> {files: [...], created_at}
# Each file entry: {file_type, filename, file_id, data}
_store: dict = {}

MAX_FILES_PER_SESSION = 5  # Gemini API practical limit for image-heavy PDFs


def create_session() -> str:
    """Create an empty multi-file session and return its ID."""
    session_id = str(uuid.uuid4())
    _store[session_id] = {
        "files": [],
        "created_at": time.time(),
    }
    return session_id


def add_file_to_session(session_id: str, file_type: str, filename: str, file_id: str, data: dict) -> bool:
    """Add a processed file to an existing session. Returns False if session missing/full."""
    session = _get_raw(session_id)
    if session is None:
        return False
    if len(session["files"]) >= MAX_FILES_PER_SESSION:
        return False
    session["files"].append({
        "file_type": file_type,
        "filename": filename,
        "file_id": file_id,
        "data": data,
    })
    return True


def get_session(session_id: str) -> Optional[dict]:
    return _get_raw(session_id)


def _get_raw(session_id: str) -> Optional[dict]:
    session = _store.get(session_id)
    if not session:
        return None
    age = time.time() - session["created_at"]
    if age > settings.session_ttl_seconds:
        del _store[session_id]
        return None
    return session


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


def get_max_files() -> int:
    return MAX_FILES_PER_SESSION