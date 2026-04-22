import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.config import settings
from app.services.file_router import detect_file_type
from app.services.dxf_parser import parse_dxf
from app.services.pdf_parser import parse_pdf
from app.services.graph_builder import build_graph
from app.db.session_store import (
    create_session,
    create_batch_session,
    add_file_to_batch,
    get_session,
)

router = APIRouter()

UPLOAD_DIR = Path(settings.upload_dir)

# Maximum number of files allowed in a single batch session
MAX_BATCH_FILES = 10


def _process_file(file_type: str, save_path: Path, file_id: str, filename: str):
    """Parse & build graph. Returns (session_data, summary)."""
    if file_type == "dxf":
        parsed = parse_dxf(str(save_path))
        graph_summary = build_graph(file_id, parsed)
        session_data = {
            "graph_summary": graph_summary,
            "graph_session_id": file_id,
            "metadata": parsed["metadata"],
            "layers": parsed["layers"],
            "entity_count": len(parsed["entities"]),
        }
        summary = {
            "layers": len(parsed["layers"]),
            "entities": len(parsed["entities"]),
            "metadata": parsed["metadata"],
        }
    else:  # pdf
        parsed = parse_pdf(str(save_path))
        session_data = {
            "chunks": parsed["chunks"],
            "full_text": parsed["full_text"],
            "page_images": parsed["page_images"],
            "metadata": parsed["metadata"],
        }
        summary = parsed["metadata"]
    return session_data, summary


# ── Single-file upload (original behaviour, kept for compatibility) ──

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        file_type = detect_file_type(file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    max_bytes = settings.max_file_size_mb * 1024 * 1024
    contents = await file.read()
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size is {settings.max_file_size_mb}MB.",
        )

    file_id = str(uuid.uuid4())
    save_path = UPLOAD_DIR / f"{file_id}_{file.filename}"
    with open(save_path, "wb") as f:
        f.write(contents)

    try:
        session_data, summary = _process_file(file_type, save_path, file_id, file.filename)
    except Exception as e:
        save_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Failed to process file: {str(e)}")

    session_id = create_session(file_type, session_data)

    return {
        "session_id": session_id,
        "file_type": file_type,
        "filename": file.filename,
        "status": "ready",
        "summary": summary,
    }


# ── Batch: create an empty session ───────────────────────────────────

@router.post("/batch/create")
async def create_batch():
    """Create a new empty batch session. Returns a batch_session_id."""
    session_id = create_batch_session()
    return {"batch_session_id": session_id, "files": [], "status": "empty"}


# ── Batch: add one file to an existing session ────────────────────────

@router.post("/batch/{batch_session_id}/add")
async def add_file_to_batch_session(
    batch_session_id: str,
    file: UploadFile = File(...),
):
    # Validate batch session exists
    session = get_session(batch_session_id)
    if not session or session.get("session_type") != "batch":
        raise HTTPException(status_code=404, detail="Batch session not found or expired.")

    # Enforce per-session file limit
    if len(session.get("files", [])) >= MAX_BATCH_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Batch limit reached. Maximum {MAX_BATCH_FILES} files per session.",
        )

    try:
        file_type = detect_file_type(file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    max_bytes = settings.max_file_size_mb * 1024 * 1024
    contents = await file.read()
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size is {settings.max_file_size_mb}MB.",
        )

    file_id = str(uuid.uuid4())
    save_path = UPLOAD_DIR / f"{file_id}_{file.filename}"
    with open(save_path, "wb") as f:
        f.write(contents)

    try:
        session_data, summary = _process_file(file_type, save_path, file_id, file.filename)
    except Exception as e:
        save_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Failed to process file: {str(e)}")

    add_file_to_batch(batch_session_id, file_type, file.filename, session_data, summary)

    # Return current state of the batch
    updated_session = get_session(batch_session_id)
    files_info = [
        {"filename": f["filename"], "file_type": f["file_type"], "summary": f["summary"]}
        for f in updated_session["files"]
    ]

    return {
        "batch_session_id": batch_session_id,
        "added": {"filename": file.filename, "file_type": file_type, "summary": summary},
        "files": files_info,
        "total_files": len(files_info),
        "status": "ready",
    }
