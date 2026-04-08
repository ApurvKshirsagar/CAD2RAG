from app.db.session_store import get_session
from app.services.graph_builder import query_graph
from app.services.gemini_client import query_with_context


def handle_query(session_id: str, question: str) -> dict:
    session = get_session(session_id)

    if not session:
        return {
            "error": "Session not found or expired. Please upload your file again.",
            "session_id": session_id
        }

    file_type = session["file_type"]

    if file_type == "dxf":
        graph_id = session["data"].get("graph_session_id", session_id)  # ← key fix
        context = query_graph(graph_id, question)
    else:
        context = _get_pdf_context(session["data"], question)

    answer = query_with_context(context, question, file_type)

    return {
        "session_id": session_id,
        "file_type": file_type,
        "question": question,
        "answer": answer,
        "context_used": context[:500] + "..." if len(context) > 500 else context
    }


def _get_pdf_context(session_data: dict, question: str) -> str:
    chunks = session_data.get("chunks", [])
    full_text = session_data.get("full_text", "")

    if len(full_text) < 8000:
        return full_text

    return "\n\n---\n\n".join(chunks[:5])