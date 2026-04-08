import time
import uuid
from typing import Optional
from app.config import settings

# In-memory store: session_id -> {file_type, data, created_at}
_store: dict = {}

def create_session(file_type: str, data: dict) -> str:
    session_id = str(uuid.uuid4())
    _store[session_id] = {
        "file_type": file_type,   # "dxf" or "pdf"
        "data": data,             # neo4j graph label OR text chunks
        "created_at": time.time()
    }
    return session_id

def get_session(session_id: str) -> Optional[dict]:
    session = _store.get(session_id)
    if not session:
        return None
    # Check TTL
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