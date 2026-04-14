from app.db.session_store import get_session
from app.services.graph_builder import query_graph
from app.services.gemini_client import query_with_context, query_with_images


def handle_query(session_id: str, question: str) -> dict:
    session = get_session(session_id)

    if not session:
        return {
            "error": "Session not found or expired. Please upload your file again.",
            "session_id": session_id
        }

    file_type = session["file_type"]

    if file_type == "dxf":
        graph_id = session["data"].get("graph_session_id", session_id)
        context = query_graph(graph_id, question)
        answer = query_with_context(context, question, file_type)

    else:  # pdf
        session_data = session["data"]
        is_image_based = session_data.get("metadata", {}).get("is_image_based", False)

        if is_image_based:
            # Send pages as images to Gemini vision
            page_images = session_data.get("page_images", [])
            answer = query_with_images(page_images, question)
            context = f"[Image-based PDF — {len(page_images)} pages sent to Gemini vision]"
        else:
            # Text-based PDF — use text context
            context = _get_pdf_context(session_data, question)
            answer = query_with_context(context, question, file_type)

    return {
        "session_id": session_id,
        "file_type": file_type,
        "question": question,
        "answer": answer,
        "context_used": context[:300] + "..." if len(context) > 300 else context
    }


def _get_pdf_context(session_data: dict, question: str) -> str:
    full_text = session_data.get("full_text", "")
    chunks = session_data.get("chunks", [])

    if len(full_text) < 8000:
        return full_text

    return "\n\n---\n\n".join(chunks[:5])