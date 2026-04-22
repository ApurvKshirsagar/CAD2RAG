from app.db.session_store import get_session
from app.services.graph_builder import query_graph
from app.services.gemini_client import query_with_context, query_with_images


def handle_query(session_id: str, question: str) -> dict:
    session = get_session(session_id)

    if not session:
        return {
            "error": "Session not found or expired. Please upload your file(s) again.",
            "session_id": session_id,
        }

    session_type = session.get("session_type", "single")

    if session_type == "batch":
        return _handle_batch_query(session_id, session, question)
    else:
        return _handle_single_query(session_id, session, question)


# ── Single-file (original) ───────────────────────────────────────────

def _handle_single_query(session_id: str, session: dict, question: str) -> dict:
    file_type = session["file_type"]

    if file_type == "dxf":
        graph_id = session["data"].get("graph_session_id", session_id)
        context = query_graph(graph_id, question)
        answer = query_with_context(context, question, file_type)
    else:
        session_data = session["data"]
        is_image_based = session_data.get("metadata", {}).get("is_image_based", False)
        if is_image_based:
            page_images = session_data.get("page_images", [])
            answer = query_with_images(page_images, question)
            context = f"[Image-based PDF — {len(page_images)} pages sent to Gemini vision]"
        else:
            context = _get_pdf_context(session_data, question)
            answer = query_with_context(context, question, file_type)

    return {
        "session_id": session_id,
        "file_type": file_type,
        "question": question,
        "answer": answer,
        "context_used": context[:300] + "..." if len(context) > 300 else context,
    }


# ── Multi-file batch ─────────────────────────────────────────────────

def _handle_batch_query(session_id: str, session: dict, question: str) -> dict:
    files = session.get("files", [])
    if not files:
        return {
            "error": "No files in this batch session. Please add files first.",
            "session_id": session_id,
        }

    # Separate image-based PDFs from text/DXF files
    image_files = []
    text_contexts = []

    for f in files:
        ftype = f["file_type"]
        fname = f["filename"]
        fdata = f["data"]

        if ftype == "dxf":
            graph_id = fdata.get("graph_session_id")
            ctx = query_graph(graph_id, question)
            text_contexts.append(f"=== DXF FILE: {fname} ===\n{ctx}")

        else:  # pdf
            is_image_based = fdata.get("metadata", {}).get("is_image_based", False)
            if is_image_based:
                for img in fdata.get("page_images", [])[:5]:
                    image_files.append((fname, img))
            else:
                ctx = _get_pdf_context(fdata, question)
                text_contexts.append(f"=== PDF FILE: {fname} ===\n{ctx}")

    combined_context = "\n\n".join(text_contexts)
    filenames = [f["filename"] for f in files]

    # Build answer
    if image_files and text_contexts:
        # Mixed: answer text part first, then images
        text_answer = query_with_context(combined_context, question, "pdf") if combined_context else ""
        img_answer = _query_batch_images(image_files, question)
        answer = _merge_answers(text_answer, img_answer, filenames)
    elif image_files:
        answer = _query_batch_images(image_files, question)
    else:
        answer = query_with_context(combined_context, question, "batch")

    ctx_preview = combined_context[:300] + "..." if len(combined_context) > 300 else combined_context

    return {
        "session_id": session_id,
        "session_type": "batch",
        "files_queried": filenames,
        "question": question,
        "answer": answer,
        "context_used": ctx_preview,
    }


# ── Helpers ──────────────────────────────────────────────────────────

def _get_pdf_context(session_data: dict, question: str) -> str:
    full_text = session_data.get("full_text", "")
    chunks = session_data.get("chunks", [])
    if len(full_text) < 8000:
        return full_text
    return "\n\n---\n\n".join(chunks[:5])


def _query_batch_images(image_files: list, question: str) -> str:
    """Send images from multiple files (labelled by filename) to Gemini vision."""
    from app.services.gemini_client import model

    system_prompt = (
        "You are an expert architectural and engineering drawing analyst.\n"
        "You are looking at scanned PDF pages from MULTIPLE files.\n"
        "Each page is labelled with its source filename.\n"
        "Answer the question accurately using information from all the provided pages.\n"
        "When referencing information, mention which file it came from."
    )

    parts = [f"{system_prompt}\n\nUser question: {question}\n\nHere are the PDF pages:"]

    for fname, img_data in image_files[:10]:  # cap at 10 images total across all files
        parts.append(f"\n[File: {fname} | Page {img_data['page_number']}]")
        parts.append({"mime_type": "image/png", "data": img_data["base64"]})

    try:
        response = model.generate_content(parts)
        return response.text
    except Exception as e:
        return f"Gemini error: {str(e)}"


def _merge_answers(text_answer: str, img_answer: str, filenames: list) -> str:
    parts = []
    if text_answer:
        parts.append(f"**From text-based files:**\n{text_answer}")
    if img_answer:
        parts.append(f"**From image-based files:**\n{img_answer}")
    return "\n\n".join(parts)
