import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from app.config import settings
from app.services.file_router import detect_file_type
from app.services.dxf_parser import parse_dxf
from app.services.pdf_parser import parse_pdf
from app.services.graph_builder import build_graph
from app.db.session_store import (
    create_session,
    add_file_to_session,
    get_session,
    get_max_files,
)

router = APIRouter()

UPLOAD_DIR = Path(settings.upload_dir)


@router.post("/session")
async def new_session():
    """Create a fresh empty session before any uploads."""
    session_id = create_session()
    return {"session_id": session_id, "max_files": get_max_files()}


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    session_id: str = Query(..., description="Session ID from /session endpoint"),
):
    # 1. Validate session
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired.")

    current_count = len(session["files"])
    if current_count >= get_max_files():
        raise HTTPException(
            status_code=400,
            detail=f"Session already has {get_max_files()} files (maximum). Start a new session to upload more.",
        )

    # 2. Validate file type
    try:
        file_type = detect_file_type(file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 3. Check file size
    max_bytes = settings.max_file_size_mb * 1024 * 1024
    contents = await file.read()
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size is {settings.max_file_size_mb}MB.",
        )

    # 4. Save to disk
    file_id = str(uuid.uuid4())
    save_path = UPLOAD_DIR / f"{file_id}_{file.filename}"
    with open(save_path, "wb") as f:
        f.write(contents)

    # 5. Parse
    try:
        if file_type == "dxf":
            parsed = parse_dxf(str(save_path))
            graph_summary = build_graph(file_id, parsed)
            file_data = {
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
            file_data = {
                "chunks": parsed["chunks"],
                "full_text": parsed["full_text"],
                "page_images": parsed["page_images"],
                "metadata": parsed["metadata"],
            }
            summary = parsed["metadata"]

    except Exception as e:
        save_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Failed to process file: {str(e)}")

    # 6. Add file to session
    add_file_to_session(session_id, file_type, file.filename, file_id, file_data)

    updated_session = get_session(session_id)
    files_in_session = len(updated_session["files"])

    return {
        "session_id": session_id,
        "file_type": file_type,
        "filename": file.filename,
        "file_id": file_id,
        "status": "ready",
        "summary": summary,
        "files_in_session": files_in_session,
        "max_files": get_max_files(),
        "slots_remaining": get_max_files() - files_in_session,
    }