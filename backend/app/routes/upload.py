import shutil
import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.config import settings
from app.services.file_router import detect_file_type
from app.services.dxf_parser import parse_dxf
from app.services.pdf_parser import parse_pdf
from app.services.graph_builder import build_graph
from app.db.session_store import create_session

router = APIRouter()

UPLOAD_DIR = Path(settings.upload_dir)


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    # 1. Validate file type
    try:
        file_type = detect_file_type(file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 2. Check file size
    max_bytes = settings.max_file_size_mb * 1024 * 1024
    contents = await file.read()
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size is {settings.max_file_size_mb}MB."
        )

    # 3. Save to disk
    file_id = str(uuid.uuid4())
    save_path = UPLOAD_DIR / f"{file_id}_{file.filename}"
    with open(save_path, "wb") as f:
        f.write(contents)

    # 4. Parse & store based on file type
    try:
        if file_type == "dxf":
            parsed = parse_dxf(str(save_path))
            graph_summary = build_graph(file_id, parsed)
            session_data = {
                "graph_summary": graph_summary,
                "graph_session_id": file_id,        # ← key fix
                "metadata": parsed["metadata"],
                "layers": parsed["layers"],
                "entity_count": len(parsed["entities"])
            }
        else:
            parsed = parse_pdf(str(save_path))
            session_data = {
                "chunks": parsed["chunks"],
                "full_text": parsed["full_text"],
                "metadata": parsed["metadata"]
            }

    except Exception as e:
        save_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Failed to process file: {str(e)}")

    # 5. Create session
    session_id = create_session(file_type, session_data)

    # 6. Return response
    response = {
        "session_id": session_id,
        "file_type": file_type,
        "filename": file.filename,
        "status": "ready"
    }

    if file_type == "dxf":
        response["summary"] = {
            "layers": len(parsed["layers"]),
            "entities": len(parsed["entities"]),
            "metadata": parsed["metadata"]
        }
    else:
        response["summary"] = parsed["metadata"]

    return response